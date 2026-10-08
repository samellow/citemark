"""The Phase 1 schema (PRD 4) and the rules the database enforces itself (T3)."""

import datetime as dt
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from citemark.db.models import (
    EMBEDDING_DIMENSIONS,
    Base,
    Chunk,
    Citation,
    Conversation,
    Document,
    Message,
    Source,
    TestQuestion,
    TestSet,
)

pytestmark = pytest.mark.anyio


async def add(session, *rows):
    session.add_all(rows)
    await session.flush()
    return rows[0] if len(rows) == 1 else rows


async def refused(session, statement, match):
    """The statement fails, and the session carries on (the failure is rolled back to a savepoint)."""
    with pytest.raises(IntegrityError, match=match):
        async with session.begin_nested():
            await session.execute(statement)


def embedding(axis=0):
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[axis] = 1.0
    return vector


async def a_chunk(session, text="Star a message: click the star icon.", axis=0):
    source = await add(session, Source(kind="start_page", url="https://zulip.com/help/"))
    document = await add(
        session,
        Document(
            source_id=source.id, url="https://zulip.com/help/star-a-message", title="Star a message", content_hash="h"
        ),
    )
    return await add(
        session,
        Chunk(
            document_id=document.id,
            position=0,
            heading_path="Star a message",
            blocks=[text],
            text=text,
            token_count=9,
            embedding=embedding(axis),
        ),
    )


async def a_cited_answer(session, chunk):
    conversation = await add(session, Conversation(model="claude-haiku-5-5", prompt_version="1"))
    message = await add(
        session, Message(conversation_id=conversation.id, role="assistant", content="Click the star.", kind="answer")
    )
    await add(
        session,
        Citation(message_id=message.id, marker=1, chunk_id=chunk.id, cited_text=chunk.text, start_block=0, end_block=1),
    )
    return conversation, message


async def a_frozen_set(session):
    test_set = await add(session, TestSet(name="zulip", version=1))
    question = await add(
        session,
        TestQuestion(test_set_id=test_set.id, ext_id="Q001", type="answerable", question="How do I star a message?"),
    )
    await session.execute(
        update(TestSet).where(TestSet.id == test_set.id).values(frozen_at=func.now(), content_hash="2766f216")
    )
    return test_set, question


async def test_the_models_match_the_migrations(session):
    connection = await session.connection()
    diff = await connection.run_sync(lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata))
    assert diff == []


async def test_ids_are_uuid_v7(session):
    first, second = (await session.execute(select(func.uuid_generate_v7(), func.uuid_generate_v7()))).one()
    source = await add(session, Source(kind="upload"))
    for value in (first, second, source.id):
        assert value.version == 7
        assert value.variant == uuid.RFC_4122
    made_at = dt.datetime.fromtimestamp(int.from_bytes(first.bytes[:6]) / 1000, dt.UTC)
    assert abs(made_at - dt.datetime.now(dt.UTC)) < dt.timedelta(minutes=1)


# QA promise 13: a frozen test set can't change


async def test_a_frozen_sets_questions_cant_change(session):
    test_set, question = await a_frozen_set(session)
    edit = update(TestQuestion).where(TestQuestion.id == question.id).values(question="How do I unstar a message?")
    await refused(session, edit, "frozen")
    await refused(session, delete(TestQuestion).where(TestQuestion.id == question.id), "frozen")
    with pytest.raises(IntegrityError, match="frozen"):
        async with session.begin_nested():
            await add(session, TestQuestion(test_set_id=test_set.id, ext_id="Q002", type="decline", question="?"))


async def test_a_frozen_set_cant_change_but_its_targets_can(session):
    test_set, _ = await a_frozen_set(session)
    this_set = TestSet.id == test_set.id
    await refused(session, update(TestSet).where(this_set).values(frozen_at=None), "frozen")
    await refused(session, update(TestSet).where(this_set).values(content_hash="edited"), "frozen")
    await refused(session, delete(TestSet).where(this_set), "frozen")
    await session.execute(update(TestSet).where(this_set).values(threshold={"answer_correctness": 0.9}))
    assert await session.scalar(select(TestSet.threshold).where(this_set)) == {"answer_correctness": 0.9}


async def test_a_draft_sets_questions_can_change(session):
    test_set = await add(session, TestSet(name="zulip", version=2))
    question = await add(session, TestQuestion(test_set_id=test_set.id, ext_id="Q001", type="partial", question="?"))
    await session.execute(update(TestQuestion).where(TestQuestion.id == question.id).values(uncovered_part="exports"))
    await session.execute(delete(TestQuestion).where(TestQuestion.id == question.id))


# QA promise 14: a citation from last month still opens its passage


async def test_chunks_are_never_deleted(session):
    chunk = await a_chunk(session)
    await refused(session, delete(Chunk).where(Chunk.id == chunk.id), "never deleted")


async def test_a_chunk_can_be_retired_once_and_never_edited(session):
    chunk = await a_chunk(session)
    this_chunk = Chunk.id == chunk.id
    await refused(session, update(Chunk).where(this_chunk).values(text="Edited."), "never edited")
    await session.execute(update(Chunk).where(this_chunk).values(retired_at=func.now()))
    await refused(session, update(Chunk).where(this_chunk).values(retired_at=func.now()), "never edited")
    await refused(session, update(Chunk).where(this_chunk).values(retired_at=None), "never edited")


async def test_a_retired_chunks_citation_still_opens_it(session):
    chunk = await a_chunk(session)
    _, message = await a_cited_answer(session, chunk)
    await session.execute(update(Chunk).where(Chunk.id == chunk.id).values(retired_at=func.now()))
    opened = await session.scalar(select(Chunk.text).join(Citation).where(Citation.message_id == message.id))
    assert opened == chunk.text


async def test_deleting_a_conversation_deletes_its_messages_and_citations(session):
    chunk = await a_chunk(session)
    conversation, message = await a_cited_answer(session, chunk)
    await session.execute(delete(Conversation).where(Conversation.id == conversation.id))
    assert await session.scalar(select(func.count()).where(Message.id == message.id)) == 0
    assert await session.scalar(select(func.count()).where(Citation.message_id == message.id)) == 0
    assert await session.scalar(select(func.count()).where(Chunk.id == chunk.id)) == 1


async def test_only_the_bots_messages_have_a_kind(session):
    conversation = await add(session, Conversation(model="claude-haiku-5-5", prompt_version="1"))
    for role, kind in (("user", "answer"), ("assistant", None)):
        with pytest.raises(IntegrityError, match="ck_message_kind_role"):
            async with session.begin_nested():
                await add(session, Message(conversation_id=conversation.id, role=role, content="Hi", kind=kind))


async def test_embeddings_round_trip_and_search_by_cosine_distance(session):
    await a_chunk(session, axis=0)
    mute = await a_chunk(session, text="Mute a channel: click the bell.", axis=1)
    stored = await session.scalar(select(Chunk.embedding).where(Chunk.id == mute.id))
    assert list(stored) == embedding(1)
    nearest = select(Chunk.id).order_by(Chunk.embedding.cosine_distance(embedding(1))).limit(1)
    assert await session.scalar(nearest) == mute.id


async def test_the_keyword_column_is_made_from_the_text(session):
    chunk = await a_chunk(session, text="Starring messages helps you find them later.")
    match = select(Chunk.id).where(Chunk.tsv.bool_op("@@")(func.websearch_to_tsquery("english", "starred message")))
    assert await session.scalar(match) == chunk.id

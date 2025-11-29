from telegram import Update, Message, Chat, User
from types import SimpleNamespace
from faker import Faker
from datetime import datetime, timezone
import random

fake = Faker()


def generate_fake_update():
    user = User(
        id=fake.random_int(min=100000, max=999999),
        is_bot=False,
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        username=fake.user_name(),
        language_code="en"
    )

    chat = Chat(
        id=random.randint(-10**12, -10**11),
        type="supergroup",
        title=fake.bs().title()
    )

    message = Message(
        message_id=random.randint(1000, 9999),
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        # text=fake.sentence(nb_words=5),
        text="/clear_state",
        channel_chat_created=False,
        delete_chat_photo=False,
        group_chat_created=False,
        supergroup_chat_created=False
    )

    update = Update(
        update_id=random.randint(500_000_000, 600_000_000),
        message=message
    )

    return update


def generate_fake_context(update):
    # Simple mock CallbackContext with required fields
    context = SimpleNamespace()
    context.args = fake.words(nb=3)
    context.user_data = {"theme": fake.color_name()}
    context.chat_data = {}
    context.bot_data = {}
    context.update = update
    return context

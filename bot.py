import discord
import asyncio
import os
import asyncpg
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

STRIKER_ROLE_ID = 1395362673088270346
DAY3_ROLE_ID = 1482377410178715729

CHECK_INTERVAL = 60  # seconds

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)

db = None


# ---------------- DATABASE ----------------

async def setup_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS striker_users (
            user_id BIGINT PRIMARY KEY,
            timestamp TIMESTAMP
        )
    """)


async def add_user(user_id):
    await db.execute("""
        INSERT INTO striker_users (user_id, timestamp)
        VALUES ($1, $2)
        ON CONFLICT (user_id)
        DO UPDATE SET timestamp = EXCLUDED.timestamp
    """, user_id, datetime.utcnow())


async def remove_user(user_id):
    await db.execute("""
        DELETE FROM striker_users WHERE user_id = $1
    """, user_id)


async def get_all_users():
    return await db.fetch("SELECT user_id, timestamp FROM striker_users")


# ---------------- ROLE CHECK LOOP ----------------

async def check_roles():
    await bot.wait_until_ready()

    while not bot.is_closed():
        rows = await get_all_users()

        for guild in bot.guilds:
            striker_role = guild.get_role(STRIKER_ROLE_ID)
            day3_role = guild.get_role(DAY3_ROLE_ID)

            for row in rows:
                user_id = row["user_id"]
                timestamp = row["timestamp"]

                member = guild.get_member(user_id)
                if not member:
                    continue

                # If striker removed → cleanup
                if striker_role not in member.roles:
                    await remove_user(user_id)
                    if day3_role in member.roles:
                        await member.remove_roles(day3_role)
                    continue

                # Check time
                if datetime.utcnow() - timestamp >= timedelta(minutes=1):
                    if day3_role not in member.roles:
                        await member.add_roles(day3_role)

        await asyncio.sleep(CHECK_INTERVAL)


# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_member_update(before, after):
    before_roles = {r.id for r in before.roles}
    after_roles = {r.id for r in after.roles}

    striker_added = STRIKER_ROLE_ID not in before_roles and STRIKER_ROLE_ID in after_roles
    striker_removed = STRIKER_ROLE_ID in before_roles and STRIKER_ROLE_ID not in after_roles

    if striker_added:
        await add_user(after.id)

    if striker_removed:
        await remove_user(after.id)

        role = after.guild.get_role(DAY3_ROLE_ID)
        if role in after.roles:
            await after.remove_roles(role)


# ---------------- STARTUP ----------------

@bot.event
async def setup_hook():
    await setup_db()
    bot.loop.create_task(check_roles())

bot.run(TOKEN)

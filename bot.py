import discord
import asyncio
import os
import asyncpg
from datetime import datetime, timedelta, UTC

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

STRIKER_ROLE_ID = 1395362673088270346
DAY3_ROLE_ID = 1482377410178715729
LOG_CHANNEL_ID = 1429229785657249884  

CHECK_INTERVAL = 60
TIME_REQUIRED = timedelta(hours=72)

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)

db = None


# ---------------- DATABASE ----------------

async def setup_db():
    global db
    db = await asyncpg.create_pool(DATABASE_URL)

    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS striker_users (
                user_id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP
            )
        """)


async def add_user(user_id):
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO striker_users (user_id, timestamp)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET timestamp = EXCLUDED.timestamp
        """, user_id, datetime.utcnow())


async def remove_user(user_id):
    async with db.acquire() as conn:
        await conn.execute("""
            DELETE FROM striker_users WHERE user_id = $1
        """, user_id)


async def get_all_users():
    async with db.acquire() as conn:
        return await conn.fetch("SELECT user_id, timestamp FROM striker_users")


# ---------------- LOGGING ----------------

async def log(guild, message):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)


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
                        await log(guild, f"❌ Removed 3day from {member} (lost Striker)")

                    continue

                # ✅ FIX TIMEZONE HERE (INSIDE LOOP)
                timestamp = timestamp.replace(tzinfo=UTC)

                # Check time
                if datetime.now(UTC) - timestamp >= TIME_REQUIRED:
                    if day3_role not in member.roles:
                        await member.add_roles(day3_role)
                        await log(guild, f"✅ Gave 3day to {member}")

        await asyncio.sleep(CHECK_INTERVAL)


# ---------------- EVENTS ----------------

@bot.event
async def setup_hook():
    await setup_db()
    bot.loop.create_task(check_roles())


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
        await log(after.guild, f"🟡 {after} got Striker → timer started")

    if striker_removed:
        await remove_user(after.id)
        await log(after.guild, f"🔴 {after} lost Striker → timer reset")

        role = after.guild.get_role(DAY3_ROLE_ID)
        if role in after.roles:
            await after.remove_roles(role)
            await log(after.guild, f"❌ Removed 3day from {after}")


# ---------------- START ----------------

bot.run(TOKEN)

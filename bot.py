import discord
import asyncio
import os

TOKEN = os.getenv("TOKEN")

STRIKER_ROLE_ID = 1395362673088270346
DAY3_ROLE_ID = 1482377410178715729

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)

timers = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

async def striker_timer(member):
    try:
        await asyncio.sleep(72 * 3600)

        member = member.guild.get_member(member.id)

        if member and any(role.id == STRIKER_ROLE_ID for role in member.roles):
            role = member.guild.get_role(DAY3_ROLE_ID)
            if role:
                await member.add_roles(role)

    except asyncio.CancelledError:
        pass


@bot.event
async def on_member_update(before, after):

    before_roles = {r.id for r in before.roles}
    after_roles = {r.id for r in after.roles}

    striker_added = STRIKER_ROLE_ID not in before_roles and STRIKER_ROLE_ID in after_roles
    striker_removed = STRIKER_ROLE_ID in before_roles and STRIKER_ROLE_ID not in after_roles

    # Striker added
    if striker_added:

        if after.id in timers:
            timers[after.id].cancel()

        task = asyncio.create_task(striker_timer(after))
        timers[after.id] = task

    # Striker removed
    if striker_removed:

        if after.id in timers:
            timers[after.id].cancel()
            del timers[after.id]

        role = after.guild.get_role(DAY3_ROLE_ID)

        if role in after.roles:
            await after.remove_roles(role)


bot.run(TOKEN)

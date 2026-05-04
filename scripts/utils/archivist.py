import os, discord, json, asyncio, traceback
from dotenv import load_dotenv
from discord.ext import commands
# from discord import app_commands

class Archivist:
    def __init__(self, async_client):
        self.async_client = async_client
        load_dotenv()
        self.discord_token: str = os.getenv("DISCORD_TOKEN")
        self.webhook_url: str = os.getenv("WEBHOOK_URL")
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.intents.messages = True
        self.bot_channel = "comic-scraper"
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self.catalogue = CatalogueManager("catalogue.json")
        # self.tree = app_commands.CommandTree(self)
    
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(self.handle_loop_exception)
        # self.register_commands()

        @self.bot.event
        async def on_ready():
            await self.bot.tree.sync()
            print(f"Logged in as {self.bot.user}")

        # @self.bot.tree.command()
        # @app_commands.describe(
        #     first_value='The first value you want to add something to',
        #     second_value='The value you want to add to the first value',
        # )
        # async def add(interaction: discord.Interaction, first_value: int, second_value: int):
        #     """Adds two numbers together."""
        #     await interaction.response.send_message(f'{first_value} + {second_value} = {first_value + second_value}')
    
    # def register_commands(self):
    #     @catalogue_group.command(name="add", description="Add a comic to catalogue.json")
    #     async def catalogue_add(
    #         interaction: discord.Interaction,
    #         name: str,
    #         domain: str,
    #         comic_id: int = 0,
    #         release_day: str = "everyday",
    #         completed: bool = False,
    #     ):
    #         added = self.catalogue.add(name, domain, comic_id, release_day, completed)

    #         if added:
    #             await interaction.response.send_message(f"✅ Added `{name}` to catalogue.")
    #         else:
    #             await interaction.response.send_message(
    #                 f"⚠️ `{name}` already exists.",
    #                 ephemeral=True
    #             )

    #     @catalogue_group.command(name="remove", description="Remove a comic from catalogue.json")
    #     async def catalogue_remove(
    #         interaction: discord.Interaction,
    #         name: str,
    #     ):
    #         removed = self.catalogue.remove(name)

    #         if removed:
    #             await interaction.response.send_message(f"🗑️ Removed `{name}`.")
    #         else:
    #             await interaction.response.send_message(
    #                 f"⚠️ Could not find `{name}`.",
    #                 ephemeral=True
    #             )

    #     @catalogue_group.command(name="find", description="Find comics in catalogue.json")
    #     async def catalogue_find(
    #         interaction: discord.Interaction,
    #         query: str,
    #     ):
    #         matches = self.catalogue.find(query)

    #         if not matches:
    #             await interaction.response.send_message("No matches found.", ephemeral=True)
    #             return

    #         lines = []
    #         for idx, comic in enumerate(matches[:10], 1):
    #             name, domain, comic_id, release_day, completed = comic
    #             lines.append(
    #                 f"`{idx}.` **{name}** | `{domain}` | id=`{comic_id}` | `{release_day}` | completed=`{completed}`"
    #             )

    #         await interaction.response.send_message("\n".join(lines))

    #     @catalogue_group.command(name="edit", description="Edit a comic field in catalogue.json")
    #     async def catalogue_edit(
    #         interaction: discord.Interaction,
    #         name: str,
    #         field: str,
    #         value: str,
    #     ):
    #         edited = self.catalogue.edit(name, field, value)

    #         if edited is None:
    #             await interaction.response.send_message(
    #                 "Could not edit comic. Fields are: "
    #                 "`name`, `domain`, `comic_id`, `release_day`, `completed`",
    #                 ephemeral=True
    #             )
    #             return

    #         await interaction.response.send_message(f"✅ Updated:\n```py\n{edited}\n```")

    #     self.bot.tree.add_command(catalogue_group)

    def handle_loop_exception(self, loop, context):
        """Global exception handler for the event loop"""
        exception = context.get('exception')
        message = context.get('message', 'Unknown error')
        
        if exception:
            asyncio.create_task(self.notify_error(f"Unhandled error: {message}", exception))
        else:
            asyncio.create_task(self.notify_error(f"Unhandled error: {message}"))

    async def run_bot(self): await self.bot.start(self.discord_token)

    async def close_bot(self): await self.bot.close()
        
    async def notify_message(self, message: str) -> None:
        await self.async_client.post(self.webhook_url, json={"content": message})

    async def mention(self):
        user_id = 292339806153998336
        await self.async_client.post(self.webhook_url, json={"content": f"<@{user_id}>"})

    async def notify_error(self, message: str, error: Exception = None) -> None:
        if error:
            tb_str = traceback.format_exc()
            if len(tb_str) > 1500: tb_str = tb_str[:1500] + "... (truncated)"
            full_message = f"🚨 **Error:** {message}\n\n```python\n{tb_str}\n```"
        else:
            full_message = f"🚨 **Error:** {message}"

        if error:
            traceback.print_exc()

        await self.async_client.post(self.webhook_url, json={"content": f"{full_message}"})

class CatalogueManager:
    def __init__(self, path="catalogue.json"):
        self.path = path

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data):
        data = sorted(data, key=lambda comic: comic[0].lower())
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, name, domain, comic_id=0, release_day="everyday", completed=False):
        data = self.load()

        if any(comic[0].lower() == name.lower() for comic in data):
            return False

        data.append([name, domain, comic_id, release_day, completed])
        self.save(data)
        return True

    def remove(self, name):
        data = self.load()
        new_data = [comic for comic in data if comic[0].lower() != name.lower()]

        if len(new_data) == len(data):
            return False

        self.save(new_data)
        return True

    def find(self, query):
        data = self.load()
        return [comic for comic in data if query.lower() in comic[0].lower()]

    def edit(self, name, field, value):
        fields = {
            "name": 0,
            "domain": 1,
            "comic_id": 2,
            "release_day": 3,
            "completed": 4,
            "status": 4,
        }

        if field not in fields:
            return None

        data = self.load()

        for comic in data:
            if comic[0].lower() == name.lower():
                idx = fields[field]

                if field == "comic_id":
                    value = int(value)
                elif field in ["completed", "status"]:
                    value = value.lower() in ["true", "yes", "1", "completed"]

                comic[idx] = value
                self.save(data)
                return comic

        return None
  

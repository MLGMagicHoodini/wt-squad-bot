import discord
from discord.ext import commands
from config import DISCORD_TOKEN
import asyncio

# Configuration
CREATE_VOICE_CHANNEL_NAME = "Create Squad Channel"  # The voice channel users join
CATEGORY_ID = None  # Optional: Category ID to create channels in (or None)
CHANNEL_PREFIX = "WT Squad"
DELETE_EMPTY_CHANNELS = True

# Bot setup
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store temporary channels and pending interactions
temp_channels = {}
pending_setups = {}


class SquadView(discord.ui.View):
    def __init__(self, user_id, voice_state):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.voice_state = voice_state
        self.message = None
    
    async def on_timeout(self):
        """Called when the view times out"""
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        if self.user_id in pending_setups:
            del pending_setups[self.user_id]
    
    async def create_squad_channel(self, interaction: discord.Interaction, size: int):
        """Create the squad channel and move the user"""
        # Determine channel name
        name_suffix = {1: "(Solo)", 2: "(Duo)", 3: "(Trio)", 4: ""}
        channel_name = f"{CHANNEL_PREFIX} {name_suffix.get(size, '')}".strip()
        
        guild = self.voice_state.channel.guild
        member = guild.get_member(self.user_id)
        
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message(
                "❌ You're no longer in a voice channel!", 
                ephemeral=True
            )
            return
        
        # Create the voice channel
        category = guild.get_channel(CATEGORY_ID) if CATEGORY_ID else None
        new_channel = await guild.create_voice_channel(
            name=channel_name,
            category=category,
            user_limit=size,
            reason=f"Squad channel created by {member.name}"
        )
        
        # Store as temp channel
        temp_channels[new_channel.id] = {
            'creator_id': self.user_id,
            'created_at': asyncio.get_event_loop().time(),
            'size': size
        }
        
        # Move user to new channel
        await member.move_to(new_channel)
        
        # Respond and clean up
        await interaction.response.send_message(
            f"✅ Created your {channel_name}! You've been moved to the channel.",
            ephemeral=True
        )
        
        # Delete the button message
        try:
            await self.message.delete()
        except:
            pass
        
        # Clean up pending setup
        if self.user_id in pending_setups:
            del pending_setups[self.user_id]
        
        print(f"✨ Created {channel_name} for {member.name} (Limit: {size})")
    
    @discord.ui.button(label="Solo (1)", style=discord.ButtonStyle.primary, emoji="1️⃣")
    async def solo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your squad creation!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 1)
    
    @discord.ui.button(label="Duo (2)", style=discord.ButtonStyle.primary, emoji="2️⃣")
    async def duo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your squad creation!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 2)
    
    @discord.ui.button(label="Trio (3)", style=discord.ButtonStyle.primary, emoji="3️⃣")
    async def trio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your squad creation!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 3)
    
    @discord.ui.button(label="Squad (4)", style=discord.ButtonStyle.success, emoji="4️⃣")
    async def squad_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your squad creation!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 4)


@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(f"📋 Monitoring for users joining '{CREATE_VOICE_CHANNEL_NAME}'")


@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state changes"""
    
    # Check if user joined the create channel
    if after.channel and after.channel.name == CREATE_VOICE_CHANNEL_NAME:
        # Don't create multiple pending setups for the same user
        if member.id in pending_setups:
            return
        
        # Create view with buttons
        view = SquadView(member.id, after)
        
        # Send message with buttons directly to the voice channel's text chat
        try:
            message = await after.channel.send(
                f"🎮 {member.mention} **War Thunder Squad Setup**\n"
                f"Select your squad size:",
                view=view
            )
            
            view.message = message
            pending_setups[member.id] = view
        except discord.Forbidden:
            print(f"❌ Bot doesn't have permission to send messages in {after.channel.name}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    # Check if a temp channel became empty
    if DELETE_EMPTY_CHANNELS and before.channel:
        await check_empty_channel(before.channel)


async def check_empty_channel(channel):
    """Delete temporary channels that are empty"""
    if channel.id not in temp_channels:
        return
    
    if len(channel.members) == 0:
        try:
            await channel.delete(reason="Squad channel empty")
            del temp_channels[channel.id]
            print(f"🗑️ Deleted empty squad channel: {channel.name}")
        except Exception as e:
            print(f"Error deleting channel: {e}")


# Run the bot
bot.run(DISCORD_TOKEN)
import discord
from discord.ext import commands
from config import DISCORD_TOKEN
import asyncio

# Configuration
CREATE_SQUAD_CHANNEL_NAME = "Criar Squad"  # Limited squad channels (1-4)
CREATE_UNLIMITED_CHANNEL_ID = 1456683516283850857  # "Criar Canal de Voz" - Unlimited channels
UNLIMITED_CATEGORY_ID = 1456683672219680962  # Category for unlimited channels
SQUAD_CATEGORY_ID = 1456072402915164294  # Optional: Category for squad channels (or None)
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


class CustomChannelModal(discord.ui.Modal, title="Nome do Canal de Voz"):
    channel_name = discord.ui.TextInput(
        label="Nome do Canal",
        placeholder="Digite o nome do seu canal...",
        max_length=100,
        required=True
    )
    
    def __init__(self, user_id, voice_state):
        super().__init__()
        self.user_id = user_id
        self.voice_state = voice_state
    
    async def on_submit(self, interaction: discord.Interaction):
        """Create the unlimited custom channel"""
        channel_name = self.channel_name.value.strip()
        
        if not channel_name:
            await interaction.response.send_message(
                "❌ O nome do canal não pode estar vazio!",
                ephemeral=True
            )
            return
        
        guild = self.voice_state.channel.guild
        member = guild.get_member(self.user_id)
        
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message(
                "❌ Você não está mais em um canal de voz!",
                ephemeral=True
            )
            return
        
        # Create the voice channel
        category = guild.get_channel(UNLIMITED_CATEGORY_ID)
        new_channel = await guild.create_voice_channel(
            name=channel_name,
            category=category,
            user_limit=0,  # Unlimited
            reason=f"Canal personalizado criado por {member.name}"
        )
        
        # Store as temp channel
        temp_channels[new_channel.id] = {
            'creator_id': self.user_id,
            'created_at': asyncio.get_event_loop().time(),
            'size': 0,
            'type': 'unlimited'
        }
        
        # Move user to new channel
        await member.move_to(new_channel)
        
        # Respond
        await interaction.response.send_message(
            f"✅ Canal **{channel_name}** criado! Você foi movido para o canal.",
            ephemeral=True
        )
        
        # Clean up pending setup
        if self.user_id in pending_setups:
            try:
                await pending_setups[self.user_id]['message'].delete()
            except:
                pass
            del pending_setups[self.user_id]
        
        print(f"✨ Created unlimited channel '{channel_name}' for {member.name}")


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
                "❌ Você não está mais em um canal de voz!",
                ephemeral=True
            )
            return
        
        # Create the voice channel
        category = guild.get_channel(SQUAD_CATEGORY_ID) if SQUAD_CATEGORY_ID else None
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
            'size': size,
            'type': 'squad'
        }
        
        # Move user to new channel
        await member.move_to(new_channel)
        
        # Respond and clean up
        await interaction.response.send_message(
            f"✅ Criado seu {channel_name}! Você foi movido para o canal.",
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
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 1)
    
    @discord.ui.button(label="Duo (2)", style=discord.ButtonStyle.primary, emoji="2️⃣")
    async def duo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 2)
    
    @discord.ui.button(label="Trio (3)", style=discord.ButtonStyle.primary, emoji="3️⃣")
    async def trio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 3)
    
    @discord.ui.button(label="Squad (4)", style=discord.ButtonStyle.success, emoji="4️⃣")
    async def squad_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 4)


class UnlimitedChannelView(discord.ui.View):
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
    
    @discord.ui.button(label="Criar Canal Personalizado", style=discord.ButtonStyle.success, emoji="🎤")
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de canal!", ephemeral=True)
            return
        
        # Show modal for channel name
        modal = CustomChannelModal(self.user_id, self.voice_state)
        await interaction.response.send_modal(modal)


@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(f"📋 Monitoring for users joining voice channels")


@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state changes"""
    
    # Check if user joined the squad create channel
    if after.channel and after.channel.name == CREATE_SQUAD_CHANNEL_NAME:
        # Don't create multiple pending setups for the same user
        if member.id in pending_setups:
            return
        
        # Create view with buttons
        view = SquadView(member.id, after)
        
        # Send message with buttons directly to the voice channel's text chat
        try:
            message = await after.channel.send(
                f"🎮 {member.mention} **War Thunder Squad Setup**\n"
                f"Selecione o tamanho do seu squad:",
                view=view,
                delete_after=35  # Auto-delete after 35 seconds
            )
            
            view.message = message
            pending_setups[member.id] = {'message': message, 'view': view}
        except discord.Forbidden:
            print(f"❌ Bot doesn't have permission to send messages in {after.channel.name}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    # Check if user joined the unlimited channel creator
    elif after.channel and after.channel.id == CREATE_UNLIMITED_CHANNEL_ID:
        # Don't create multiple pending setups for the same user
        if member.id in pending_setups:
            return
        
        # Create view with button to open modal
        view = UnlimitedChannelView(member.id, after)
        
        # Send message with button
        try:
            message = await after.channel.send(
                f"🎤 {member.mention} **Criar Canal de Voz**\n"
                f"Clique no botão para criar seu canal personalizado:",
                view=view,
                delete_after=35  # Auto-delete after 35 seconds
            )
            
            view.message = message
            pending_setups[member.id] = {'message': message, 'view': view}
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
            await channel.delete(reason="Canal vazio - auto-deletado")
            del temp_channels[channel.id]
            print(f"🗑️ Deleted empty channel: {channel.name}")
        except Exception as e:
            print(f"Error deleting channel: {e}")


# Run the bot
bot.run(DISCORD_TOKEN)
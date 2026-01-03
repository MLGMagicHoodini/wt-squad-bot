import discord
from discord.ext import commands, tasks
from config import DISCORD_TOKEN
import asyncio
import re

# Configuration
CREATE_SQUAD_CHANNEL_ID = 1457130530872234156  # Squad channel creator (1-4 players)
CREATE_UNLIMITED_CHANNEL_ID = 1456683516283850857  # "Criar Canal de Voz" - Unlimited channels
UNLIMITED_CATEGORY_ID = 1456683672219680962  # Category for unlimited channels
SQUAD_CATEGORY_ID = 1456072402915164294  # Optional: Category for squad channels (or None)
DELETE_EMPTY_CHANNELS = True

# Bot setup
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store temporary channels and pending interactions
temp_channels = {}
pending_setups = {}


def get_next_channel_number(guild, category_id, channel_prefix):
    """Find the next available number for a channel name pattern"""
    # Get the category or all channels if no category
    if category_id:
        category = guild.get_channel(category_id)
        channels = category.voice_channels if category else []
    else:
        channels = guild.voice_channels
    
    existing_numbers = []
    # Match pattern like "Solo 1", "Duo 2", "Geral 3", etc.
    pattern = re.compile(rf'{re.escape(channel_prefix)}\s*(\d+)')
    
    for channel in channels:
        match = pattern.match(channel.name)
        if match:
            existing_numbers.append(int(match.group(1)))
    
    if not existing_numbers:
        return 1
    
    # Find the lowest available number
    existing_numbers.sort()
    for i in range(1, max(existing_numbers) + 2):
        if i not in existing_numbers:
            return i
    
    return max(existing_numbers) + 1


class CustomChannelModal(discord.ui.Modal, title="Nome do Canal de Voz"):
    channel_name = discord.ui.TextInput(
        label="Nome do Canal",
        placeholder="Deixe em branco para 'Geral X'",
        max_length=100,
        required=False
    )
    
    def __init__(self, user_id, voice_state):
        super().__init__()
        self.user_id = user_id
        self.voice_state = voice_state
    
    async def on_submit(self, interaction: discord.Interaction):
        """Create the unlimited custom channel"""
        channel_name = self.channel_name.value.strip()
        
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        
        # Check if user is still in voice
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message(
                "❌ Você não está mais em um canal de voz!",
                ephemeral=True
            )
            return
        
        # If no name provided, use "Geral X"
        if not channel_name:
            next_number = get_next_channel_number(guild, UNLIMITED_CATEGORY_ID, "Geral")
            channel_name = f"Geral {next_number}"
        
        # Create the voice channel
        category = guild.get_channel(UNLIMITED_CATEGORY_ID)
        
        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                user_limit=0,  # Unlimited
                reason=f"Canal personalizado criado por {member.name}"
            )
            
            # Try to move user to new channel
            try:
                await member.move_to(new_channel)
                
                # Only add to temp_channels if user was successfully moved
                temp_channels[new_channel.id] = {
                    'creator_id': self.user_id,
                    'created_at': asyncio.get_event_loop().time(),
                    'size': 0,
                    'type': 'unlimited'
                }
                
                await interaction.response.send_message(
                    f"✅ Canal **{channel_name}** criado! Você foi movido para o canal.",
                    ephemeral=True
                )
                
                print(f"✨ Created unlimited channel '{channel_name}' for {member.name}")
                
            except discord.Forbidden:
                # Couldn't move user, delete the channel
                await new_channel.delete(reason="Não foi possível mover o usuário")
                await interaction.response.send_message(
                    "❌ Não foi possível mover você para o canal. Permissões insuficientes.",
                    ephemeral=True
                )
            except discord.HTTPException:
                # User might have disconnected, delete the channel
                await new_channel.delete(reason="Usuário desconectou")
                await interaction.response.send_message(
                    "❌ Você desconectou antes de ser movido. Tente novamente.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error creating channel: {e}")
            await interaction.response.send_message(
                "❌ Erro ao criar o canal. Tente novamente.",
                ephemeral=True
            )
        
        # Clean up pending setup
        if self.user_id in pending_setups:
            try:
                await pending_setups[self.user_id]['message'].delete()
            except:
                pass
            del pending_setups[self.user_id]


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
    
    async def create_squad_channel(self, interaction: discord.Interaction, size: int, size_name: str):
        """Create the squad channel and move the user"""
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        
        # Check if user is still in voice
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message(
                "❌ Você não está mais em um canal de voz!",
                ephemeral=True
            )
            return
        
        # Get next number for this squad size
        next_number = get_next_channel_number(guild, SQUAD_CATEGORY_ID, size_name)
        channel_name = f"{size_name} {next_number}"
        
        # Create the voice channel
        category = guild.get_channel(SQUAD_CATEGORY_ID) if SQUAD_CATEGORY_ID else None
        
        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                user_limit=size,
                reason=f"Squad channel created by {member.name}"
            )
            
            # Try to move user to new channel
            try:
                await member.move_to(new_channel)
                
                # Only add to temp_channels if user was successfully moved
                temp_channels[new_channel.id] = {
                    'creator_id': self.user_id,
                    'created_at': asyncio.get_event_loop().time(),
                    'size': size,
                    'type': 'squad'
                }
                
                await interaction.response.send_message(
                    f"✅ Criado seu {channel_name}! Você foi movido para o canal.",
                    ephemeral=True
                )
                
                print(f"✨ Created {channel_name} for {member.name} (Limit: {size})")
                
            except discord.Forbidden:
                # Couldn't move user, delete the channel
                await new_channel.delete(reason="Não foi possível mover o usuário")
                await interaction.response.send_message(
                    "❌ Não foi possível mover você para o canal. Permissões insuficientes.",
                    ephemeral=True
                )
            except discord.HTTPException:
                # User might have disconnected, delete the channel
                await new_channel.delete(reason="Usuário desconectou")
                await interaction.response.send_message(
                    "❌ Você desconectou antes de ser movido. Tente novamente.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error creating channel: {e}")
            await interaction.response.send_message(
                "❌ Erro ao criar o canal. Tente novamente.",
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
    
    @discord.ui.button(label="Solo (1)", style=discord.ButtonStyle.primary, emoji="1️⃣")
    async def solo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 1, "Solo")
    
    @discord.ui.button(label="Duo (2)", style=discord.ButtonStyle.primary, emoji="2️⃣")
    async def duo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 2, "Duo")
    
    @discord.ui.button(label="Trio (3)", style=discord.ButtonStyle.primary, emoji="3️⃣")
    async def trio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 3, "Trio")
    
    @discord.ui.button(label="Squad (4)", style=discord.ButtonStyle.success, emoji="4️⃣")
    async def squad_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este não é o seu setup de squad!", ephemeral=True)
            return
        await self.create_squad_channel(interaction, 4, "Squad")


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
        
        # Show modal for channel name (this opens a popup, doesn't create instantly)
        modal = CustomChannelModal(self.user_id, self.voice_state)
        await interaction.response.send_modal(modal)


@bot.event
async def on_ready():
    cleanup_empty_channels.start()  # Start the cleanup task
    print(f"✅ Bot is online as {bot.user}")
    print(f"📋 Monitoring squad channel: {CREATE_SQUAD_CHANNEL_ID}")
    print(f"📋 Monitoring unlimited channel: {CREATE_UNLIMITED_CHANNEL_ID}")


@tasks.loop(minutes=5)
async def cleanup_empty_channels():
    """Periodic cleanup of empty temp channels (backup safety net)"""
    if not DELETE_EMPTY_CHANNELS:
        return
    
    for channel_id in list(temp_channels.keys()):
        channel = bot.get_channel(channel_id)
        if channel:
            if len(channel.members) == 0:
                try:
                    await channel.delete(reason="Canal vazio - limpeza periódica")
                    del temp_channels[channel_id]
                    print(f"🧹 Cleaned up empty channel: {channel.name}")
                except Exception as e:
                    print(f"Error cleaning channel {channel_id}: {e}")
        else:
            # Channel doesn't exist anymore, remove from tracking
            del temp_channels[channel_id]


@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state changes"""
    
    # Check if user joined the squad create channel
    if after.channel and after.channel.id == CREATE_SQUAD_CHANNEL_ID:
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
                f"Clique no botão abaixo para escolher o nome do canal:",
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
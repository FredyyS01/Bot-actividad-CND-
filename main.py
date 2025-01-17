from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import pytz
import os
import asyncio
from discord.errors import HTTPException

app = Flask('')

@app.route('/')
def home():
    return "Bot Activo!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():    
    server = Thread(target=run)
    server.start()

# Configuración del bot con intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Configuración del bot con opciones para manejar rate limits
bot = commands.Bot(
    command_prefix='/',
    intents=intents,
    max_messages=10000,
    chunk_guilds_at_startup=False
)

# Colores y configuración
COLOR_NARANJA = 0xFF8C00
COLOR_ERROR = 0xFF0000
ZONA_HORARIA = pytz.timezone('America/Argentina/Buenos_Aires')
trabajando = {}

async def manejar_rate_limit():
    await asyncio.sleep(5)  # Esperar 5 segundos antes de reintentar

@bot.event
async def on_ready():
    try:
        print(f'Bot conectado como: {bot.user.name}')
        await asyncio.sleep(1)  # Pequeña pausa antes de sincronizar
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

def obtener_hora_servidor():
    return datetime.datetime.now(ZONA_HORARIA)

class TerminarView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Terminar Labor", style=discord.ButtonStyle.danger)
    async def terminar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user_id and not any(role.name.lower() == "directivo" for role in interaction.user.roles):
                embed_error = discord.Embed(
                    title="⚠️ Error",
                    description="Solo el periodista que inició el servicio o un directivo puede terminarlo.",
                    color=COLOR_ERROR
                )
                await interaction.response.send_message(embed=embed_error, ephemeral=True)
                return

            if self.user_id in trabajando:
                tiempo_inicio = trabajando[self.user_id]
                tiempo_final = obtener_hora_servidor()
                duracion = tiempo_final - tiempo_inicio.astimezone(ZONA_HORARIA)
                
                horas = int(duracion.total_seconds() // 3600)
                minutos = int((duracion.total_seconds() % 3600) // 60)
                segundos = int(duracion.total_seconds() % 60)
                
                embed = discord.Embed(
                    title="🎯 Servicio Finalizado",
                    description=f"El periodista {interaction.user.mention} ha salido de servicio periodístico.",
                    color=COLOR_NARANJA
                )
                embed.add_field(
                    name="⏱️ Tiempo en servicio",
                    value=f"{horas}h {minutos}m {segundos}s",
                    inline=False
                )
                embed.add_field(
                    name="🕒 Hora de finalización (Hora SV)",
                    value=tiempo_final.strftime("%H:%M:%S"),
                    inline=False
                )
                
                del trabajando[self.user_id]
                
                await interaction.message.delete()
                await asyncio.sleep(0.5)  # Pequeña pausa entre operaciones
                await interaction.channel.send(embed=embed)
            else:
                embed_error = discord.Embed(
                    title="⚠️ Error",
                    description="No se encontró el registro de inicio de servicio.",
                    color=COLOR_ERROR
                )
                await interaction.response.send_message(embed=embed_error, ephemeral=True)
        except HTTPException as e:
            if e.status == 429:  # Rate limit error
                await manejar_rate_limit()
                await interaction.followup.send("Por favor, intenta nuevamente en unos segundos.", ephemeral=True)
            else:
                raise e

@bot.tree.command(name="trabajar", description="Iniciar servicio periodístico")
async def trabajar(interaction: discord.Interaction):
    try:
        if interaction.user.id in trabajando:
            embed_error = discord.Embed(
                title="⚠️ Error",
                description="Ya tienes un servicio activo en este momento.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)
            return

        hora_inicio = obtener_hora_servidor()
        trabajando[interaction.user.id] = hora_inicio
        
        embed = discord.Embed(
            title="📰 Inicio de Servicio",
            description=f"El periodista {interaction.user.mention} ha entrado en servicio periodístico.",
            color=COLOR_NARANJA
        )
        embed.add_field(
            name="⏰ Hora de inicio (Hora SV)",
            value=hora_inicio.strftime("%H:%M:%S"),
            inline=False
        )

        view = TerminarView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        
    except HTTPException as e:
        if e.status == 429:  # Rate limit error
            await manejar_rate_limit()
            await interaction.followup.send("Por favor, intenta nuevamente en unos segundos.", ephemeral=True)
        else:
            raise e

# Manejo de errores global
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error en el evento {event}: {args[0]}")

# Iniciar el bot con manejo de reconexión
async def start_bot():
    try:
        await bot.start(os.environ['DISCORD_TOKEN'])
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")
        await asyncio.sleep(5)
        await start_bot()

# Mantener el bot vivo
keep_alive()

# Iniciar el bot con manejo de errores
try:
    asyncio.run(start_bot())
except Exception as e:
    print(f"Error crítico: {e}")

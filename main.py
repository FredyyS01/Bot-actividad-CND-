from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import pytz
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot Activo!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():    
    server = Thread(target=run)
    server.start()

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Color naranja para los embeds
COLOR_NARANJA = 0xFF8C00  # Código hexadecimal para naranja
COLOR_ERROR = 0xFF0000    # Rojo para errores

# Zona horaria
ZONA_HORARIA = pytz.timezone('America/Argentina/Buenos_Aires')

# Diccionario para almacenar los tiempos de inicio y motivos de los periodistas
trabajando = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como: {bot.user.name}')
    try:
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
        if interaction.user.id != self.user_id and not any(role.name.lower() == "directivo" for role in interaction.user.roles):
            embed_error = discord.Embed(
                title="⚠️ Error",
                description="Solo el periodista que inició el servicio o un directivo puede terminarlo.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)
            return

        if self.user_id in trabajando:
            tiempo_inicio = trabajando[self.user_id]['tiempo']
            motivo = trabajando[self.user_id]['motivo']
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
                name="📋 Motivo del servicio",
                value=motivo,
                inline=False
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
            
            # Eliminar el mensaje original
            await interaction.message.delete()
            
            # Enviar el mensaje de finalización
            await interaction.channel.send(embed=embed)
        else:
            embed_error = discord.Embed(
                title="⚠️ Error",
                description="No se encontró el registro de inicio de servicio.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)

@bot.tree.command(name="trabajar", description="Iniciar servicio periodístico")
async def trabajar(interaction: discord.Interaction, motivo: str):
    if interaction.user.id in trabajando:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Ya tienes un servicio activo en este momento.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if not motivo or motivo.isspace():
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Debes especificar el motivo del servicio.\nEjemplo: `/trabajar Transmisión de radio`",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    hora_inicio = obtener_hora_servidor()
    trabajando[interaction.user.id] = {
        'tiempo': hora_inicio,
        'motivo': motivo
    }
    
    embed = discord.Embed(
        title="📰 Inicio de Servicio",
        description=f"El periodista {interaction.user.mention} ha entrado en servicio periodístico.",
        color=COLOR_NARANJA
    )
    embed.add_field(
        name="📋 Motivo",
        value=motivo,
        inline=False
    )
    embed.add_field(
        name="⏰ Hora de inicio (Hora SV)",
        value=hora_inicio.strftime("%H:%M:%S"),
        inline=False
    )

    view = TerminarView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

# Iniciar el bot
keep_alive()
token = os.environ['DISCORD_TOKEN']
bot.run(token)

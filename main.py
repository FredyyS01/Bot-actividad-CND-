from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import os

# Configuración de Flask
app = Flask('')

@app.route('/')
def home():
    return "Bot Activo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():    
    server = Thread(target=run)
    server.start()

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

trabajando = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como: {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

class TerminarView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Terminar Labor", style=discord.ButtonStyle.danger)
    async def terminar_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id and not any(role.name.lower() == "directivo" for role in interaction.user.roles):
            await interaction.response.send_message("Solo el periodista que inició el servicio o un directivo puede terminarlo.", ephemeral=True)
            return

        if self.user_id in trabajando:
            tiempo_inicio = trabajando[self.user_id]
            tiempo_final = datetime.datetime.now()
            duracion = tiempo_final - tiempo_inicio
            
            horas = duracion.seconds // 3600
            minutos = (duracion.seconds % 3600) // 60
            segundos = duracion.seconds % 60
            
            embed = discord.Embed(
                title="🎯 Servicio Finalizado",
                description=f"El periodista {interaction.user.mention} ha salido de servicio periodístico.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="⏱️ Tiempo en servicio",
                value=f"{horas}h {minutos}m {segundos}s",
                inline=False
            )
            
            del trabajando[self.user_id]
            
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Error: No se encontró el registro de inicio de servicio.", ephemeral=True)

@bot.tree.command(name="trabajar", description="Iniciar servicio periodístico")
async def trabajar(interaction: discord.Interaction):
    if interaction.user.id in trabajando:
        await interaction.response.send_message("Ya tienes un servicio activo en este momento.", ephemeral=True)
        return

    trabajando[interaction.user.id] = datetime.datetime.now()
    
    embed = discord.Embed(
        title="📰 Inicio de Servicio",
        description=f"El periodista {interaction.user.mention} ha entrado en servicio periodístico.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="⏰ Hora de inicio",
        value=trabajando[interaction.user.id].strftime("%H:%M:%S"),
        inline=False
    )

    view = TerminarView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view)

if __name__ == '__main__':
    keep_alive()
    token = os.environ['DISCORD_TOKEN']
    try:
        bot.run(token)
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")

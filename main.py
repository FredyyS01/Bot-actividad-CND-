from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ui import Button, View
import datetime
import asyncio
import os
from dotenv import load_dotenv
import logging
import time

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Configuración del servidor web
app = Flask('')
app.logger.setLevel(logging.INFO)

@app.route('/')
def home():
    return "¡Bot está en línea!"

@app.route('/ping')
def ping():
    return "Pong!"

def run_flask():
    try:
        app.run(host='0.0.0.0', port=8080, debug=False)
    except Exception as e:
        app.logger.error(f"Error en el servidor web: {e}")

def keep_alive():
    try:
        print("Iniciando servidor web...")
        server_thread = Thread(target=run_flask, daemon=True)
        server_thread.start()
        print("Servidor web iniciado en:")
        print(f"https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co")
    except Exception as e:
        print(f"Error al iniciar el servidor web: {e}")

# Cargar variables de entorno
load_dotenv()

# Obtener el token
TOKEN = os.getenv('DISCORD_TOKEN')

# Diccionario para almacenar los tiempos de inicio de los periodistas
trabajando = {}

# Configurar intents específicamente
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True

class TerminarButton(Button):
    def __init__(self, user_id: int):
        super().__init__(style=discord.ButtonStyle.danger, label="Terminar Labor", custom_id=f"terminar_{user_id}")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id and not any(role.name.lower() == "directivo" for role in interaction.user.roles):
            embed = discord.Embed(
                title="⚠️ Error",
                description="El servicio solo puede ser terminado por el periodista que lo activó o un directivo.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
                description=f"El periodista {interaction.guild.get_member(self.user_id).mention} ha salido de servicio periodístico.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="⏱️ Tiempo en servicio",
                value=f"{horas}h {minutos}m {segundos}s",
                inline=False
            )
            
            del trabajando[self.user_id]
            
            self.disabled = True
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message("Error: No se encontró el registro de inicio de servicio.", ephemeral=True)

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        try:
            await self.tree.sync()
            print("Comandos sincronizados correctamente")
        except Exception as e:
            print(f"Error al sincronizar comandos: {e}")

client = Bot()

@client.event
async def on_ready():
    try:
        print(f'Bot conectado como {client.user}')
        print(f'ID del bot: {client.user.id}')
        print('-------------------')
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Periodistas en servicio"))
    except Exception as e:
        print(f"Error en on_ready: {e}")

@client.tree.command(name="trabajar", description="Iniciar servicio periodístico")
async def trabajar(interaction: discord.Interaction):
    try:
        if interaction.user.id in trabajando:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Ya tienes el comando activado en este momento.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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

        view = View(timeout=None)
        view.add_item(TerminarButton(interaction.user.id))
        
        await interaction.response.send_message(embed=embed, view=view)
    except Exception as e:
        print(f"Error en comando trabajar: {e}")
        await interaction.response.send_message("Ocurrió un error al procesar el comando.", ephemeral=True)

def main():
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            if not TOKEN:
                raise ValueError("No se encontró el token de Discord.")
            
            print("Iniciando el bot...")
            keep_alive()  # Iniciar el servidor web
            client.run(TOKEN)
            break  # Si el bot se ejecuta correctamente, salir del bucle
            
        except Exception as e:
            retry_count += 1
            print(f"Error al iniciar el bot (intento {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                print(f"Reintentando en 10 segundos...")
                time.sleep(10)
            else:
                print("Se alcanzó el número máximo de intentos. El bot no pudo iniciarse.")

if __name__ == "__main__":
    main()
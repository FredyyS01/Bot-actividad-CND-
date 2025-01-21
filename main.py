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

# Colores para los embeds
COLOR_NARANJA = 0xFF8C00  # Código hexadecimal para naranja
COLOR_ERROR = 0xFF0000    # Rojo para errores

# Zona horaria
ZONA_HORARIA = pytz.timezone('America/Argentina/Buenos_Aires')

# Diccionarios para almacenamiento
trabajando = {}
sueldos = {}

# Configuración del canal de sueldos
CANAL_SUELDOS_ID = 1331364663874551859  # Reemplazar con el ID de tu canal
mensaje_sueldos_id = None

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

async def actualizar_mensaje_sueldos(channel):
    global mensaje_sueldos_id
    
    if not sueldos:
        embed = discord.Embed(
            title="📊 Registro de Sueldos",
            description="No hay sueldos registrados actualmente.",
            color=COLOR_NARANJA
        )
    else:
        embed = discord.Embed(
            title="📊 Registro de Sueldos",
            description="Lista actualizada de sueldos pendientes:",
            color=COLOR_NARANJA
        )
        
        total_general = 0
        lista_sueldos = []
        
        for user_id, monto in sueldos.items():
            usuario = await bot.fetch_user(user_id)
            lista_sueldos.append(f"**{usuario.name}**: ${monto:,}")
            total_general += monto
        
        embed.add_field(
            name="💰 Sueldos Pendientes",
            value="\n".join(lista_sueldos),
            inline=False
        )
        embed.add_field(
            name="💵 Total General",
            value=f"${total_general:,}",
            inline=False
        )
    
    # Actualizar o enviar nuevo mensaje
    if mensaje_sueldos_id:
        try:
            mensaje = await channel.fetch_message(mensaje_sueldos_id)
            await mensaje.edit(embed=embed)
        except:
            mensaje = await channel.send(embed=embed)
            mensaje_sueldos_id = mensaje.id
    else:
        mensaje = await channel.send(embed=embed)
        mensaje_sueldos_id = mensaje.id

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

@bot.tree.command(name="agregar-paga", description="Agregar paga a un integrante")
async def agregar_paga(interaction: discord.Interaction, usuario: discord.Member, valor: int):
    # Verificar si el usuario tiene permiso (debe ser directivo)
    if not any(role.name.lower() == "directivo" for role in interaction.user.roles):
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Solo los directivos pueden gestionar los sueldos.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if valor <= 0:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="El valor debe ser mayor a 0.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Agregar o actualizar el sueldo
    if usuario.id in sueldos:
        sueldos[usuario.id] += valor
    else:
        sueldos[usuario.id] = valor

    # Actualizar mensaje en el canal de sueldos
    canal_sueldos = bot.get_channel(CANAL_SUELDOS_ID)
    await actualizar_mensaje_sueldos(canal_sueldos)

    embed = discord.Embed(
        title="✅ Paga Agregada",
        description=f"Se ha agregado ${valor:,} al sueldo de {usuario.mention}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="retirar-dinero", description="Retirar dinero del sueldo de un integrante")
async def retirar_dinero(interaction: discord.Interaction, usuario: discord.Member, valor: int):
    # Verificar si el usuario tiene permiso
    if not any(role.name.lower() == "directivo" for role in interaction.user.roles):
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Solo los directivos pueden gestionar los sueldos.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if usuario.id not in sueldos:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Este usuario no tiene sueldo registrado.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if valor <= 0:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="El valor debe ser mayor a 0.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if valor > sueldos[usuario.id]:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="El valor a retirar es mayor que el saldo disponible.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Retirar el dinero
    sueldos[usuario.id] -= valor
    if sueldos[usuario.id] == 0:
        del sueldos[usuario.id]

    # Actualizar mensaje en el canal de sueldos
    canal_sueldos = bot.get_channel(CANAL_SUELDOS_ID)
    await actualizar_mensaje_sueldos(canal_sueldos)

    embed = discord.Embed(
        title="💸 Dinero Retirado",
        description=f"Se han retirado ${valor:,} del sueldo de {usuario.mention}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="limpiar", description="Limpiar todos los registros de sueldos")
async def limpiar(interaction: discord.Interaction):
    # Verificar si el usuario tiene permiso
    if not any(role.name.lower() == "directivo" for role in interaction.user.roles):
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Solo los directivos pueden limpiar los registros de sueldos.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Confirmar que hay algo que limpiar
    if not sueldos:
        embed_error = discord.Embed(
            title="ℹ️ Información",
            description="No hay registros de sueldos para limpiar.",
            color=COLOR_NARANJA
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Guardar total antes de limpiar
    total_limpiado = sum(sueldos.values())
    
    # Limpiar registros
    sueldos.clear()

    # Actualizar mensaje en el canal de sueldos
    canal_sueldos = bot.get_channel(CANAL_SUELDOS_ID)
    await actualizar_mensaje_sueldos(canal_sueldos)

    embed = discord.Embed(
        title="🧹 Registros Limpiados",
        description=f"Se han limpiado todos los registros de sueldos.\nTotal liquidado: ${total_limpiado:,}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

# Iniciar el bot
keep_alive()
token = os.environ['DISCORD_TOKEN']
bot.run(token)

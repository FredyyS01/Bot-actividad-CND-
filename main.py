from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import pytz
import os
from datetime import timedelta
import aiohttp
import re

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

# Definir rangos y pagos por hora
RANGOS_PAGOS = {
    "practicante": 15000,
    "periodista": 16000,
    "reportero": 17000,
    "supervisor": 18000,
    "vice director": 20000
}

# Diccionarios para almacenamiento
trabajando = {}
sueldos = {}
servicios_finalizados = {}  # Diccionario para servicios finalizados

# Configuración de canales
CANAL_SUELDOS_ID = 1295477203898859610  # Reemplazar con el ID de tu canal
CANAL_EVIDENCIAS_ID = 1336202299311394827  # Reemplazar con el ID de tu canal de evidencias

# ID del mensaje de sueldos (debes reemplazar con el ID real del mensaje que quieres editar)
MENSAJE_SUELDOS_ID = 1410733674764435507  # Aquí debes poner el ID del mensaje que quieres que el bot edite siempre

# Función para obtener el nombre a mostrar (apodo o nombre de usuario)
def get_display_name(member):
    return member.nick if member.nick else member.name

# Función para obtener el pago por hora según el rango
def obtener_pago_por_hora(member):
    for role in member.roles:
        role_name = role.name.lower()
        if role_name in RANGOS_PAGOS:
            return RANGOS_PAGOS[role_name]
    # Si no tiene ningún rol de los definidos, se asume practicante
    return RANGOS_PAGOS["practicante"]

# Función para calcular el pago según el tiempo trabajado
def calcular_pago(pago_por_hora, duracion):
    # Convertir la duración a horas (como número decimal)
    horas_trabajadas = duracion.total_seconds() / 3600
    # Calcular el pago proporcional al tiempo trabajado
    pago_total = int(pago_por_hora * horas_trabajadas)
    return pago_total

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

async def actualizar_mensaje_sueldos():
    global MENSAJE_SUELDOS_ID

    canal_sueldos = bot.get_channel(CANAL_SUELDOS_ID)
    if not canal_sueldos:
        print("Error: No se pudo encontrar el canal de sueldos")
        return

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
            member = canal_sueldos.guild.get_member(user_id)
            if member:
                display_name = get_display_name(member)
                lista_sueldos.append(f"**{display_name}**: ${monto:,}")
            else:
                try:
                    usuario = await bot.fetch_user(user_id)
                    lista_sueldos.append(f"**{usuario.name}**: ${monto:,}")
                except:
                    lista_sueldos.append(f"**Usuario desconocido**: ${monto:,}")
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

    # Si tenemos un ID de mensaje específico, intentamos editarlo
    if MENSAJE_SUELDOS_ID:
        try:
            mensaje = await canal_sueldos.fetch_message(MENSAJE_SUELDOS_ID)
            await mensaje.edit(embed=embed)
            print(f"Mensaje de sueldos actualizado (ID: {MENSAJE_SUELDOS_ID})")
        except discord.NotFound:
            print(f"Mensaje con ID {MENSAJE_SUELDOS_ID} no encontrado, creando nuevo mensaje")
            mensaje = await canal_sueldos.send(embed=embed)
            MENSAJE_SUELDOS_ID = mensaje.id
            print(f"Nuevo mensaje de sueldos creado (ID: {MENSAJE_SUELDOS_ID})")
        except Exception as e:
            print(f"Error al editar mensaje de sueldos: {e}")
            mensaje = await canal_sueldos.send(embed=embed)
            MENSAJE_SUELDOS_ID = mensaje.id
    else:
        # Si no tenemos ID, creamos un nuevo mensaje
        mensaje = await canal_sueldos.send(embed=embed)
        MENSAJE_SUELDOS_ID = mensaje.id
        print(f"Mensaje de sueldos creado (ID: {MENSAJE_SUELDOS_ID})")

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

            # Calcular pago según rango y tiempo
            pago_por_hora = obtener_pago_por_hora(interaction.guild.get_member(self.user_id))
            pago_total = calcular_pago(pago_por_hora, duracion)

            servicios_finalizados[self.user_id] = {
                'tiempo_fin': tiempo_final,
                'duracion': duracion,
                'motivo': motivo,
                'tiempo_inicio': tiempo_inicio,
                'pago': pago_total
            }

            # Agregar el pago al sueldo del usuario
            if self.user_id in sueldos:
                sueldos[self.user_id] += pago_total
            else:
                sueldos[self.user_id] = pago_total

            # Actualizar mensaje de sueldos
            await actualizar_mensaje_sueldos()

            horas = int(duracion.total_seconds() // 3600)
            minutos = int((duracion.total_seconds() % 3600) // 60)
            segundos = int(duracion.total_seconds() % 60)

            # Obtener el apodo del usuario
            member = interaction.guild.get_member(self.user_id)
            display_name = get_display_name(member)

            embed = discord.Embed(
                title="🎯 Servicio Finalizado",
                description=f"El periodista {interaction.guild.get_member(self.user_id).mention} ha salido de servicio periodístico.",
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
                name="💰 Pago por servicio",
                value=f"${pago_total:,}",
                inline=False
            )
            embed.add_field(
                name="🕒 Hora de finalización (Hora SV)",
                value=tiempo_final.strftime("%H:%M:%S"),
                inline=False
            )
            embed.add_field(
                name="📝 Recordatorio",
                value="Tienes 5 minutos para enviar las evidencias usando el comando `/evidencia`",
                inline=False
            )

            del trabajando[self.user_id]
            await interaction.message.delete()
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
    # Primero verificamos si el usuario tiene un servicio activo
    if interaction.user.id in trabajando:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Ya tienes un servicio activo en este momento.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Verificamos si el usuario tiene un servicio pendiente de evidencias
    if interaction.user.id in servicios_finalizados:
        tiempo_actual = obtener_hora_servidor()
        tiempo_fin = servicios_finalizados[interaction.user.id]['tiempo_fin']
        tiempo_restante = timedelta(minutes=5) - (tiempo_actual - tiempo_fin)

        if tiempo_restante > timedelta(0):
            # Aún está dentro del período de 5 minutos
            minutos = int(tiempo_restante.total_seconds() // 60)
            segundos = int(tiempo_restante.total_seconds() % 60)
            embed_error = discord.Embed(
                title="⚠️ Error",
                description=f"Tienes un servicio pendiente de evidencias.\\n"
                           f"Debes enviar las evidencias del servicio anterior usando `/evidencia` o esperar "
                           f"{minutos}m {segundos}s para que expire el tiempo límite.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)
            return
        else:
            # Si ya pasaron los 5 minutos, eliminamos el registro pendiente
            del servicios_finalizados[interaction.user.id]

    # Verificamos que el motivo no esté vacío
    if not motivo or motivo.isspace():
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Debes especificar el motivo del servicio.\\nEjemplo: `/trabajar Transmisión de radio`",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    # Si pasa todas las verificaciones, iniciamos el nuevo servicio
    hora_inicio = obtener_hora_servidor()
    trabajando[interaction.user.id] = {
        'tiempo': hora_inicio,
        'motivo': motivo
    }

    # Usar el apodo en lugar del nombre de usuario
    display_name = get_display_name(interaction.user)

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

@bot.tree.command(name="evidencia", description="Anexar evidencias de tu servicio finalizado")
async def evidencia(
    interaction: discord.Interaction, 
    imagen1: discord.Attachment = None,
    imagen2: discord.Attachment = None,
    imagen3: discord.Attachment = None,
):
    usuario_id = interaction.user.id

    if usuario_id not in servicios_finalizados:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="No tienes un servicio finalizado recientemente o aún estás en servicio.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    tiempo_actual = obtener_hora_servidor()
    tiempo_fin = servicios_finalizados[usuario_id]['tiempo_fin']
    if tiempo_actual - tiempo_fin > timedelta(minutes=5):
        del servicios_finalizados[usuario_id]
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Han pasado más de 5 minutos desde que finalizaste tu servicio. Ya no puedes enviar evidencias.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if not any([imagen1, imagen2, imagen3]):
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Debes proporcionar al menos una evidencia.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    canal_evidencias = bot.get_channel(CANAL_EVIDENCIAS_ID)
    await interaction.response.defer()

    servicio_info = servicios_finalizados[usuario_id]
    duracion = servicio_info['duracion']
    horas = int(duracion.total_seconds() // 3600)
    minutos = int((duracion.total_seconds() % 3600) // 60)
    segundos = int(duracion.total_seconds() % 60)

    # Usar el apodo en lugar del nombre de usuario
    display_name = get_display_name(interaction.user)

    embed = discord.Embed(
        title="📊 Registro de Actividad",
        description=f"Evidencias enviadas por {interaction.user.mention}",
        color=COLOR_NARANJA
    )
    embed.add_field(
        name="⏱️ Duración del Servicio",
        value=f"{horas}h {minutos}m {segundos}s",
        inline=False
    )
    embed.add_field(
        name="📋 Motivo del Servicio",
        value=servicio_info['motivo'],
        inline=False
    )
    embed.add_field(
        name="💰 Pago por servicio",
        value=f"${servicio_info['pago']:,}",
        inline=False
    )
    embed.add_field(
        name="🕒 Inicio del Servicio",
        value=servicio_info['tiempo_inicio'].strftime("%H:%M:%S"),
        inline=True
    )
    embed.add_field(
        name="🕒 Fin del Servicio",
        value=servicio_info['tiempo_fin'].strftime("%H:%M:%S"),
        inline=True
    )

    archivos = []
    evidencias_count = 0

    if imagen1 and imagen1.content_type.startswith(('image/', 'video/')):
        archivos.append(await imagen1.to_file())
        evidencias_count += 1

    if imagen2 and imagen2.content_type.startswith(('image/', 'video/')):
        archivos.append(await imagen2.to_file())
        evidencias_count += 1

    if imagen3 and imagen3.content_type.startswith(('image/', 'video/')):
        archivos.append(await imagen3.to_file())
        evidencias_count += 1

    if evidencias_count > 0:
        embed.add_field(
            name="📎 Total de Evidencias",
            value=f"Se adjuntaron {evidencias_count} evidencia(s)",
            inline=False
        )

        await canal_evidencias.send(embed=embed, files=archivos)

        del servicios_finalizados[usuario_id]
        embed_success = discord.Embed(
            title="✅ Evidencias Enviadas",
            description=f"Se han registrado correctamente {evidencias_count} evidencia(s).",
            color=COLOR_NARANJA
        )
        await interaction.followup.send(embed=embed_success)
    else:
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="No se pudo procesar ninguna de las evidencias proporcionadas.",
            color=COLOR_ERROR
        )
        await interaction.followup.send(embed=embed_error, ephemeral=True)

@bot.tree.command(name="agregar-paga", description="Agregar paga a un integrante")
async def agregar_paga(interaction: discord.Interaction, usuario: discord.Member, valor: int):
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

    if usuario.id in sueldos:
        sueldos[usuario.id] += valor
    else:
        sueldos[usuario.id] = valor

    await actualizar_mensaje_sueldos()

    # Usar el apodo en lugar del nombre de usuario
    display_name = get_display_name(usuario)

    embed = discord.Embed(
        title="✅ Paga Agregada",
        description=f"Se ha agregado ${valor:,} al sueldo de {usuario.mention}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="retirar-dinero", description="Retirar dinero del sueldo de un integrante")
async def retirar_dinero(interaction: discord.Interaction, usuario: discord.Member, valor: int):
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

    sueldos[usuario.id] -= valor
    if sueldos[usuario.id] == 0:
        del sueldos[usuario.id]

    await actualizar_mensaje_sueldos()

    # Usar el apodo en lugar del nombre de usuario
    display_name = get_display_name(usuario)

    embed = discord.Embed(
        title="💸 Dinero Retirado",
        description=f"Se han retirado ${valor:,} del sueldo de {usuario.mention}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="limpiar-sueldos", description="Limpiar todos los registros de sueldos")
async def limpiar(interaction: discord.Interaction):
    if not any(role.name.lower() == "directivo" for role in interaction.user.roles):
        embed_error = discord.Embed(
            title="⚠️ Error",
            description="Solo los directivos pueden limpiar los registros de sueldos.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    if not sueldos:
        embed_error = discord.Embed(
            title="ℹ️ Información",
            description="No hay registros de sueldos para limpiar.",
            color=COLOR_NARANJA
        )
        await interaction.response.send_message(embed=embed_error, ephemeral=True)
        return

    total_limpiado = sum(sueldos.values())
    sueldos.clear()

    await actualizar_mensaje_sueldos()

    embed = discord.Embed(
        title="🧹 Registros Limpiados",
        description=f"Se han limpiado todos los registros de sueldos.\\nTotal liquidado: ${total_limpiado:,}",
        color=COLOR_NARANJA
    )
    await interaction.response.send_message(embed=embed)

# Iniciar el bot
keep_alive()
token = os.environ['DISCORD_TOKEN']
bot.run(token)

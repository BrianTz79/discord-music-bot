# -*- coding: utf-8 -*-
"""
Pedro Bot (TellezBot)

Un bot de música multifuncional para Discord, construido con discord.py.
Soporta reproducción desde YouTube y Spotify (canciones y playlists),
gestión de colas, y comandos de moderación personalizados.
"""

# ------------------- LIBRERÍAS -------------------
import os
import asyncio
import random
import datetime
from dotenv import load_dotenv

import discord
from discord.ext import commands
from spotdl import Spotdl
import yt_dlp
from bs4 import BeautifulSoup
import requests


# ------------------- CONFIGURACIÓN E INICIALIZACIÓN -------------------

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# --- Constantes ---
YDL_OPTS_GENERIC = {'format': 'bestaudio/best', 'quiet': True}
YDL_OPTS_SEARCH = {'format': 'bestaudio/best', 'default_search': 'ytsearch', 'quiet': True, 'extract_flat': 'in_playlist'}
YDL_OPTS_SINGLE_SEARCH = {'format': 'bestaudio/best', 'default_search': 'ytsearch1', 'quiet': True}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

# --- Inicialización de Clientes y Bot ---
# Es recomendable usar tus propias claves para mayor estabilidad.
spotdl_client = Spotdl(
    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
    headless=True
)

# Define los "intents" (permisos) que el bot necesita.
intents = discord.Intents.default()
intents.message_content = True

# Crea la instancia del bot, define el prefijo y desactiva el comando de ayuda por defecto.
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)

# Estructura de datos para manejar las colas de música por servidor.
# Formato: { guild_id: [lista_de_canciones] }
music_queues = {}


# ------------------- EVENTOS DEL BOT -------------------

@bot.event
async def on_ready():
    """Se ejecuta cuando el bot se conecta exitosamente a Discord."""
    print(f'¡Conectado como {bot.user.name} (ID: {bot.user.id})!')
    print('------------------------------------')


# ------------------- FUNCIONES AUXILIARES DE MÚSICA -------------------

async def play_next(ctx: commands.Context):
    """
    Función recursiva que reproduce la siguiente canción en la cola de un servidor.
    Se llama a sí misma como callback cuando una canción termina.
    """
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if not (voice_client and voice_client.is_connected()):
            return

        # Saca la siguiente canción de la cola.
        next_song = music_queues[guild_id].pop(0)
        
        try:
            # Define la función síncrona que se ejecutará en un hilo separado para no bloquear.
            def get_audio_url_sync(url):
                with yt_dlp.YoutubeDL(YDL_OPTS_GENERIC) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return info['url']

            # Ejecuta la obtención de la URL en el executor para no congelar el bot.
            audio_url = await bot.loop.run_in_executor(None, get_audio_url_sync, next_song['webpage_url'])

            if not audio_url:
                raise ValueError("No se pudo obtener una URL de audio válida.")

            # El callback asegura que esta función se llame de nuevo cuando la canción termine.
            callback = lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            
            voice_client.play(source, after=callback)
            await ctx.send(f'▶️ Ahora suena: **{next_song["title"]}**')

        except Exception as e:
            await ctx.send(f"❌ Error al intentar reproducir **{next_song['title']}**: `{e}`. Saltando a la siguiente.")
            # Llama a play_next en una nueva tarea para continuar con la cola.
            asyncio.create_task(play_next(ctx))
    else:
        await ctx.send("🎵 La cola de reproducción ha terminado.")

async def process_spotify_playlist_background(ctx: commands.Context, spotify_songs: list):
    """
    Procesa una lista de canciones de Spotify en segundo plano, buscando cada una
    en YouTube y añadiéndola a la cola del servidor.
    """
    guild_id = ctx.guild.id
    songs_added_count = 0
    for i, song in enumerate(spotify_songs):
        try:
            youtube_query = f"{song.name} {song.artist} Audio"
            
            def search_sync(query):
                with yt_dlp.YoutubeDL(YDL_OPTS_SINGLE_SEARCH) as ydl:
                    return ydl.extract_info(query, download=False)

            youtube_info = await bot.loop.run_in_executor(None, search_sync, youtube_query)

            if youtube_info and 'entries' in youtube_info:
                video = youtube_info['entries'][0]
                music_queues[guild_id].append({
                    'title': video.get('title', 'N/A'),
                    'webpage_url': video.get('webpage_url')
                })
                songs_added_count += 1
        except Exception as e:
            print(f"Error procesando canción en segundo plano '{song.name}': {e}")
            continue
    
    await ctx.send(f"✅ Procesamiento en segundo plano finalizado. Se añadieron **{songs_added_count}** canciones más a la cola.")


# ------------------- COMANDOS DE MÚSICA -------------------

@bot.command(name='play', help='Añade una canción o playlist a la cola (YouTube/Spotify).')
async def play(ctx: commands.Context, *, query: str):
    """
    Comando principal para la reproducción. Maneja URLs de YouTube, Spotify
    y búsquedas de texto. Optimizado para no bloquear y con reproducción
    inmediata para playlists de Spotify.
    """
    if not ctx.author.voice:
        await ctx.send("⚠️ No estás conectado a un canal de voz."); return

    channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    if ctx.guild.id not in music_queues:
        music_queues[ctx.guild.id] = []

    # Función síncrona que contiene toda la lógica de búsqueda para ser ejecutada en un hilo.
    def full_search_sync(search_query):
        initial_songs, background_songs = [], None
        
        if "spotify.com" in search_query:
            spotify_results = spotdl_client.search([search_query])
            if not spotify_results:
                return None, "No se encontraron canciones para ese enlace de Spotify."
            
            first_song = spotify_results[0]
            yt_query = f"{first_song.name} {first_song.artist} Audio"
            with yt_dlp.YoutubeDL(YDL_OPTS_SINGLE_SEARCH) as ydl:
                yt_info = ydl.extract_info(yt_query, download=False)
                if yt_info and 'entries' in yt_info:
                    video = yt_info['entries'][0]
                    initial_songs.append({'title': video.get('title'), 'webpage_url': video.get('webpage_url')})
                    background_songs = spotify_results[1:]
                    return initial_songs, background_songs
                else:
                    return None, "No se pudo encontrar la primera canción de la playlist en YouTube."
        else: # Búsqueda en YouTube
            with yt_dlp.YoutubeDL(YDL_OPTS_SEARCH) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if 'entries' in info: # Es una playlist de YouTube
                    for entry in info['entries']:
                        initial_songs.append({'title': entry.get('title'), 'webpage_url': entry.get('url')})
                else: # Es una canción única
                    initial_songs.append({'title': info.get('title'), 'webpage_url': info.get('webpage_url')})
                return initial_songs, None

    await ctx.send(f"🔄 Procesando: `{query}`...")
    # Ejecuta toda la búsqueda en un hilo separado.
    initial_songs, background_task_songs = await bot.loop.run_in_executor(None, full_search_sync, query)

    if not initial_songs:
        await ctx.send(f"❌ {background_task_songs or 'No se encontraron resultados.'}"); return

    music_queues[ctx.guild.id].extend(initial_songs)
    
    # Informa al usuario sobre lo que se añadió.
    if len(initial_songs) > 1:
        await ctx.send(f"✅ Se añadieron **{len(initial_songs)}** canciones de la playlist de YouTube.")
    elif not background_task_songs: # Solo si no es una playlist de Spotify
        await ctx.send(f"✅ **{initial_songs[0]['title']}** añadida a la cola.")

    # Inicia la tarea en segundo plano si hay canciones de Spotify pendientes.
    if background_task_songs:
        await ctx.send(f"▶️ Empezando a reproducir... El resto de la playlist de Spotify se añadirá en segundo plano.")
        asyncio.create_task(process_spotify_playlist_background(ctx, background_task_songs))

    # Inicia la reproducción si el bot estaba inactivo.
    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_next(ctx)

@bot.command(name='skip', help='Salta a la siguiente canción.')
async def skip(ctx: commands.Context):
    """Para la canción actual, lo que activa el callback 'after' para reproducir la siguiente."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Canción saltada.")
    else:
        await ctx.send("No hay ninguna canción que saltar.")

@bot.command(name='queue', help='Muestra la cola de reproducción.')
async def queue(ctx: commands.Context):
    """Muestra las canciones pendientes en la cola del servidor."""
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        embed = discord.Embed(title="🎵 Cola de Reproducción 🎵", color=discord.Color.blue())
        queue_list = "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(music_queues[guild_id][:10])])
        embed.description = queue_list
        if len(music_queues[guild_id]) > 10:
            embed.set_footer(text=f"... y {len(music_queues[guild_id]) - 10} más.")
        await ctx.send(embed=embed)
    else:
        await ctx.send("La cola está vacía.")

@bot.command(name='shuffle', help='Mezcla la cola.')
async def shuffle(ctx: commands.Context):
    """Reordena aleatoriamente la cola de canciones."""
    guild_id = ctx.guild.id
    if guild_id in music_queues and len(music_queues[guild_id]) > 1:
        random.shuffle(music_queues[guild_id])
        await ctx.send("🔀 ¡La cola ha sido mezclada!")
    else:
        await ctx.send("No hay suficientes canciones para mezclar.")

@bot.command(name='clear', help='Limpia la cola de canciones pendientes.')
async def clear(ctx: commands.Context):
    """Elimina todas las canciones de la cola, excepto la que está sonando."""
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id]:
        music_queues[guild_id].clear()
        await ctx.send("✅ La cola de canciones pendientes ha sido limpiada.")
    else:
        await ctx.send("La cola ya está vacía.")

@bot.command(name='stop', aliases=['leave'], help='Detiene la música y desconecta al bot.')
async def stop(ctx: commands.Context):
    """Limpia la cola, detiene la reproducción y desconecta al bot del canal de voz."""
    guild_id = ctx.guild.id
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        if guild_id in music_queues:
            music_queues[guild_id].clear()
        voice_client.stop()
        await voice_client.disconnect()
        await ctx.send("👋 Bot desconectado y cola limpiada.")
    else:
        await ctx.send("El bot no está en un canal de voz.")

@bot.command(name='pause', help='Pausa la reproducción.')
async def pause(ctx: commands.Context):
    """Pausa el reproductor de audio."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Pausado.")
    else:
        await ctx.send("No hay nada que pausar.")

@bot.command(name='resume', help='Reanuda la reproducción.')
async def resume(ctx: commands.Context):
    """Reanuda el reproductor de audio si estaba en pausa."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Reanudado.")
    else:
        await ctx.send("No hay nada que reanudar.")


# ------------------- COMANDOS DE MODERACIÓN -------------------

@bot.command(name='Juan', help='Comando de moderación especial.')
@commands.has_permissions(moderate_members=True)
async def juan(ctx: commands.Context):
    """Suspende a un usuario específico por 1 minuto tras una cuenta atrás."""
    USER_ID_TO_TIMEOUT = 703748051491225662 # ID del usuario objetivo

    try:
        target_member = await ctx.guild.fetch_member(USER_ID_TO_TIMEOUT)
    except discord.NotFound:
        await ctx.send("No se pudo encontrar al usuario objetivo en este servidor."); return

    await ctx.send(f"Iniciando protocolo de eliminación para {target_member.display_name}...")
    for i in range(3, 0, -1):
        await ctx.send(f"{i}...")
        await asyncio.sleep(1)
    
    try:
        duration = datetime.timedelta(minutes=1)
        await target_member.timeout(duration, reason="El martillo de Juan ha hablado.")
        await ctx.send(f"💥 ¡Listo! {target_member.mention} ha sido enviado al rincón por 1 minuto.")
    except discord.Forbidden:
        await ctx.send("❌ **Error de permisos:** Mi rol no es lo suficientemente alto o no tengo el permiso 'Moderar Miembros'.")

@juan.error
async def juan_error(ctx: commands.Context, error: commands.CommandError):
    """Manejador de errores para el comando 'juan'."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("No tienes los permisos necesarios para usar este comando.")


# ------------------- COMANDO DE AYUDA -------------------

@bot.command(name='help', aliases=['ayuda', 'comandos'], help='Muestra este mensaje de ayuda.')
async def help_command(ctx: commands.Context):
    """Muestra un panel de ayuda con todos los comandos disponibles."""
    embed = discord.Embed(
        title=f"🎧 Comandos de {bot.user.name} 🎧",
        description="Lista de comandos para controlar al bot. El prefijo es `$`.",
        color=discord.Color.from_rgb(29, 185, 84) # Verde Spotify
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else discord.Embed.Empty)

    embed.add_field(name="$play <búsqueda/URL>", value="Añade una canción/playlist de YouTube o Spotify.", inline=False)
    embed.add_field(name="$pause", value="Pausa la canción.", inline=True)
    embed.add_field(name="$resume", value="Reanuda la canción.", inline=True)
    embed.add_field(name="$skip", value="Salta a la siguiente.", inline=True)
    embed.add_field(name="$queue", value="Muestra la cola.", inline=False)
    embed.add_field(name="$clear", value="Limpia la cola.", inline=True)
    embed.add_field(name="$shuffle", value="Mezcla la cola.", inline=True)
    embed.add_field(name="$stop / $leave", value="Detiene y desconecta.", inline=True)
    embed.add_field(name="$Juan", value="Activa el protocolo de moderación especial.", inline=False)
    
    embed.set_footer(text=f"Solicitado por: {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
    await ctx.send(embed=embed)


# ------------------- EJECUCIÓN DEL BOT -------------------

if __name__ == "__main__":
    # Esta sección solo se ejecuta cuando el archivo es corrido directamente.
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("ERROR: El token del bot no fue encontrado. Asegúrate de tener un archivo .env válido.")
    else:
        bot.run(TOKEN)
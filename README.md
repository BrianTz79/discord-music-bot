# TellezBot - Bot de Música para Discord

Un bot de música y moderación multifuncional para Discord, construido desde cero con `discord.py`. Este proyecto está diseñado para ser robusto, soportando múltiples fuentes de audio y diseñado para correr 24/7 en un entorno Linux como una Raspberry Pi.

## !help 
<img width="593" height="388" alt="Screenshot 2025-07-31 002442" src="https://github.com/user-attachments/assets/92e30409-2d93-4cdd-8840-fa239d1f5950" />

---

# Si gustas puedes invitar a este bot de discord a tu servidor de discord sin problemas.

https://discord.com/oauth2/authorize?client_id=1355347301689721056&permissions=3213312&integration_type=0&scope=bot+applications.commands

Actualmente esta siendo hosteado en mi RSP 5 desde mi hogar.

---

## 🎵 Características Principales

* **Reproducción de Audio de Alta Calidad:** Soporte para YouTube y Spotify.
* **Gestión de Playlists:** Añade playlists completas desde YouTube o Spotify con un solo comando.
* **Sistema de Cola Avanzado:** Comandos intuitivos para gestionar la cola de reproducción:
    * `$play`: Añade canciones o playlists.
    * `$skip`: Salta a la siguiente canción.
    * `$queue`: Muestra la lista de espera.
    * `$clear`: Limpia la cola.
    * `$shuffle`: Mezcla el orden de las canciones.
* **Controles de Reproducción:** Incluye `$pause` y `$resume`.
* **Comandos de Moderación:** Funciones personalizadas como el comando `$Juan` para suspender usuarios.
* **Optimización de Rendimiento:** El código utiliza hilos de ejecución para manejar tareas pesadas (búsquedas en red) sin afectar la calidad del audio o la capacidad de respuesta del bot.

---

## ⚙️ Configuración e Instalación

Sigue estos pasos para poner en marcha tu propia instancia del bot.

**1. Clonar el Repositorio**
```bash
git clone [https://github.com/BrianTz79/discord-music-bot.git](https://github.com/BrianTz79/discord-music-bot.git)
cd discord-music-bot
```

**2. Crear y Activar un Entorno Virtual**
```bash
# Para Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Para Windows
python -m venv venv
venv\Scripts\activate
```

**3. Instalar las Dependencias**
```bash
pip install -r requirements.txt
```

**4. Configurar las Credenciales**

Crea un archivo llamado `.env` en la raíz del proyecto y añade tus credenciales. **Este archivo no debe ser compartido.**

```env
# Archivo .env
DISCORD_TOKEN="AQUI_VA_TU_TOKEN_DE_DISCORD"

# Claves de Spotify (Recomendadas para estabilidad)
SPOTIFY_CLIENT_ID="TU_ID_DE_CLIENTE_DE_SPOTIFY"
SPOTIFY_CLIENT_SECRET="TU_SECRETO_DE_CLIENTE_DE_SPOTIFY"
```

**5. Ejecutar el Bot**
```bash
python bot.py
```

---

## 📝 Lista de Comandos

El prefijo por defecto es `$`.

| Comando                 | Alias              | Descripción                                                |
| ----------------------- | ------------------ | ---------------------------------------------------------- |
| `help`                  | `ayuda`, `comandos`  | Muestra el panel de ayuda con todos los comandos.          |
| `play <búsqueda/URL>`   | -                  | Añade una canción o playlist a la cola.                    |
| `pause`                 | -                  | Pausa la canción actual.                                   |
| `resume`                | -                  | Reanuda la canción pausada.                                |
| `skip`                  | -                  | Salta a la siguiente canción de la cola.                   |
| `queue`                 | -                  | Muestra la lista de canciones en espera.                   |
| `clear`                 | -                  | Limpia la cola de canciones pendientes.                    |
| `shuffle`               | -                  | Mezcla el orden de las canciones en la cola.               |
| `stop`                  | `leave`            | Detiene la música, limpia la cola y desconecta al bot.     |
| `Juan`                  | -                  | Activa un comando de moderación especial.                  |

---

## 🚀 Despliegue 24/7

Este bot está preparado para ser desplegado como un servicio `systemd` en un servidor Linux (idealmente una Raspberry Pi), asegurando su funcionamiento continuo y su reinicio automático en caso de fallo.

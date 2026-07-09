# CupidX • The Ultimate Discord Assistant

CupidX is a high-performance, multipurpose Discord bot designed for modern servers. From advanced ticketing systems to seamless music playback and robust moderation, CupidX is built to provide a premium experience for both staff and members.

## 🚀 Features

### 🎧 Music System
- **High Quality Audio**: Powered by Lavalink for crystal-clear music.
- **Multiple Platforms**: Supports Spotify, YouTube, SoundCloud, and JioSaavn.
- **Interactive Controls**: Modern UI with buttons for playback, loop, shuffle, and autoplay.
- **Auto-Player Display**: Generates beautiful dynamic images for currently playing tracks.

### 🎫 Advanced Ticketing
- **Interactive Wizard**: setup your ticket system in minutes with `/addpanel`.
- **Role Selection**: easily choose staff roles from a searchable dropdown menu.
- **Transcripts**: standard text transcripts for all closed tickets.
- **Persistent Views**: User-friendly buttons for closing, claiming, and calling staff.

### 🎙️ Join2Create (Private VCs)
- **Automatic Setup**: Create private rooms instantly by joining a base channel.
- **Control Panel**: Manage your temporary voice channel (lock, hide, rename, bitrate) via an interactive panel.
- **Auto-Cleanup**: Automatically deletes empty voice channels to keep your server clean.

### 🛡️ Moderation & Automod
- **Robust Tools**: Ban, kick, mute, nuke, and lock commands with logging support.
- **Anti-Nuke**: Protect your server from malicious actions with advanced anti-nuke features.
- **Automod**: Filter invites, links, and spam messages automatically.

### 📊 Utility & Fun
- **Global Stats**: Real-time bot statistics via a built-in API.
- **Custom Roles**: Let users manage their own custom roles.
- **Welcome System**: Beautiful greeting messages for new members.

## 🛠️ Installation

### Prerequisites
- Python 3.10+
- A Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- A Lavalink server (pre-configured in `cogs/commands/music.py`)

### Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/itsmegowtham/cupidx.git
   cd cupidx
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory and add your bot token:
   ```env
   TOKEN=your_discord_bot_token_here
   ```

4. **Run the Bot**:
   ```bash
   python main.py
   ```

## 🌐 API Information
CupidX includes a built-in API for displaying stats on your website.
- **Stats Endpoint**: `http://localhost:8000/stats`
- **Output**: JSON containing server count, user count, and online status.

---

Built with ❤️ by **CupidX HQ**
# 🎪 Virtual Twin: Stage & Venue Visualizer

A GenAI-powered tool that turns an event theme into an interactive 3D venue you can walk around before you book it.

## The Problem

2D photos make it hard to imagine how a venue will look and feel on the day. Planners and families end up guessing where tables, lights and the stage will go.

## The Solution

Describe your event (for example, "Cyberpunk birthday party with neon lights"), enter the room size and guest count, and the app:

1. Asks **Gemini** to act as a scene designer and return a structured JSON layout.
2. Validates the layout so every object stays inside the room.
3. Renders it as a **3D room with Three.js** that you can rotate, zoom and pan.

## Features

- 📋 **Planner tab:** budget breakdown (table and chart), countdown timeline, tick-box vendor checklist with progress, and personalised ideas for theme, decor, food, activities and return gifts
- ⬇️ Download the full plan as Markdown, and ask for changes like "make it cheaper"
- 🔗 The 3D tab compares the decor estimate with the decor budget from your plan
- 🎨 Theme-based 3D venue generation (neon, royal, jungle and more)
- 🪑 Auto-placed tables, chairs, stage, banner, dance floor and coloured lights
- 🖱️ Interactive view: drag to orbit, scroll to zoom, right-drag to pan
- 💬 "Change something" box: ask for edits like "move the stage to the left" or "make the lights purple"
- 💰 Rough decor cost estimate (in INR) based on the items in the layout
- ✅ Layout validation so unknown object types and out-of-bounds positions are fixed automatically

## Tech Stack

- [Streamlit](https://streamlit.io/) for the UI
- [Gemini API](https://ai.google.dev/) for scene design
- [Three.js](https://threejs.org/) for 3D rendering
- Python 3

## How to Run

1. Clone the repo:
   ```
   git clone https://github.com/nandinichiliveru030-commits/venue-visualizer.git
   cd venue-visualizer
   ```
2. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
3. Start the app:
   ```
   python -m streamlit run app.py
   ```
4. Paste your Gemini API key in the sidebar. You can create one for free at https://aistudio.google.com/apikey.

### Using Streamlit secrets (optional)

Instead of typing the key each time, create `.streamlit/secrets.toml`:

```
GEMINI_API_KEY = "your-key-here"
```

This file is listed in `.gitignore`, so it is never uploaded to GitHub.

## How It Works

```
Theme + room size + guests
        │
        ▼
 Gemini (scene designer) ──► JSON layout
        │
        ▼
 Validation (clamp to room, allowed object types only)
        │
        ▼
 Three.js 3D scene (orbit controls, glowing lights)
```

## Screenshots

Add your screenshots here, for example:

| Cyberpunk | Royal Wedding | Jungle |
|-----------|---------------|--------|
| ![cyberpunk](screenshots/cyberpunk.png) | ![royal](screenshots/royal.png) | ![jungle](screenshots/jungle.png) |

## Demo

- 🎥 Demo video: https://youtu.be/jbMPkzpaGuo

## Future Ideas

- Save and reload plans, and share the vendor checklist with family
- Drag-and-drop editing of objects in the 3D view
- Export the layout as an image or PDF to share with family and vendors

## Author

Nandini ([@nandinichiliveru030-commits](https://github.com/nandinichiliveru030-commits))


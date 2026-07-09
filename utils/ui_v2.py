import discord
from discord.ui import LayoutView, Container, TextDisplay, Separator

def v2_card(title: str, body: str):
    """Create CupidX-Style v2 card."""
    view = LayoutView()
    container = Container()
    container.add_item(TextDisplay(f"**{title}**"))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    view.add_item(container)
    return view


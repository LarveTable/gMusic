from discord import ui
from collections import deque

# The view used to display the waiting list (LayoutView to use discord's v2 components)
class ListLayout(ui.LayoutView):    
    def __init__(self, waitlist: deque, current: dict):
        super().__init__(timeout=None)

        # Title
        self.add_item(ui.TextDisplay(content="### 📋 Waiting list"))
        self.add_item(ui.Separator())

        # Current song playing
        self.add_item(ui.TextDisplay(content=f"👉 {current["title"]}"))
        self.add_item(ui.Separator())

        # Next song
        if (len(waitlist) != 0):
            self.add_item(ui.TextDisplay(content=f"↪️ {waitlist[0]["title"]}"))
            self.add_item(ui.Separator())

        # Display the next songs
        for data in list(waitlist)[1:6]:
            self.add_item(ui.TextDisplay(content=data["title"]))
            self.add_item(ui.Separator())
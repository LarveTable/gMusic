from discord import ui
import discord

# The view used to display the favorites list (LayoutView to use discord's v2 components)
class FavoritesLayout(ui.LayoutView):    
    def __init__(self, favorites):
        super().__init__(timeout=60)
        self.favorites = favorites
        self.page = 1
        # Calculate the maximum number of pages (6 favorites per page)
        self.max_page = max(1, (len(self.favorites) + 5) // 6)
        # Display the favorites
        self.display_favorites()
                
    def display_favorites(self):
        # Clear the view
        self.clear_items()
        # Title
        self.add_item(ui.TextDisplay(content="### 📋 Favorites list"))
        self.add_item(ui.Separator())
        # If the user has no favorites, display a message
        if len(self.favorites) == 0:
            self.add_item(ui.TextDisplay(content="You have no favorites yet."))
        else:
            # Display 6 favorites
            for data in self.favorites[(self.page-1)*6:self.page*6]:
                self.add_item(ui.TextDisplay(content=f"**{data['title']}**"))
                self.add_item(ui.TextDisplay(content=data['webpage_url']))
                self.add_item(ui.Separator())

        # Add the pagination buttons
        action_row = ui.ActionRow()
    
        prev_button = ui.Button(label="Previous", style=discord.ButtonStyle.primary)
        prev_button.callback = self.previous_button
        prev_button.disabled = self.page == 1 # Disable if on the first page
        
        page_button = ui.Button(label=f"Page {self.page}/{self.max_page}", disabled=True)
        
        next_button = ui.Button(label="Next", style=discord.ButtonStyle.primary)
        next_button.callback = self.next_button
        next_button.disabled = self.page >= self.max_page # Disable if on the last page
        
        action_row.add_item(prev_button)
        action_row.add_item(page_button)
        action_row.add_item(next_button)
        
        self.add_item(action_row)
    
    # When the user presses the previous button
    async def previous_button(self, interaction: discord.Interaction):
        if self.page > 1:
            self.page -= 1
            self.display_favorites()
        await interaction.response.edit_message(view=self)

    # When the user presses the next button
    async def next_button(self, interaction: discord.Interaction):
        if self.page < self.max_page:
            self.page += 1
            self.display_favorites()
        await interaction.response.edit_message(view=self)
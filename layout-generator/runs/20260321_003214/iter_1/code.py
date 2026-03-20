# Set background color for the canvas
T.layout["background"] = "#1a4378"

# 1. Add Background Elements
# Using the textured vertical strip as a subtle side accent
bg_texture = T.add_element("image", src=ASSETS["5_element_0"], x=0, y=0, w=300, h=1080)
T.update_style(bg_texture, opacity=0.1)

# Main illustration: The "movie night" sofa graphic
hero_illustration = T.add_element("image", src=ASSETS["0_element_1"], x=900, y=200, w=900, h=800)

# Add decorative star elements for a "cinematic" feel
star1 = T.add_element("image", src=ASSETS["4_element_27"], x=100, y=100, w=200, h=200)
star2 = T.add_element("image", src=ASSETS["4_element_28"], x=1700, y=100, w=100, h=100)

# 2. Add Text Elements
# Headline
headline = T.add_element(
    "text", 
    text="MOVIE NIGHT", 
    x=100, y=250, w=800, h=200,
    fontFamily="Bungee", 
    fontSize=140, 
    textFill="#ffffff", 
    align="left"
)

# Subheadline/Date
date_text = T.add_element(
    "text", 
    text="FRIDAY, OCTOBER 27TH | 7:00 PM", 
    x=100, y=400, w=800, h=100,
    fontFamily="Bebas Neue", 
    fontSize=60, 
    textFill="#ffdf00", 
    align="left"
)

# Body Text/Invitation Details
details = T.add_element(
    "text", 
    text="Join us for an evening of classic films, popcorn, and good company.\n\nBring your favorite blanket and get cozy!\n\n123 Cinema Lane, Movie Town", 
    x=100, y=550, w=600, h=300,
    fontFamily="Quicksand", 
    fontSize=32, 
    textFill="#ffffff", 
    align="left",
    lineHeight=1.5
)

# 3. Add Decorative Elements
# Add a ticket graphic near the bottom for style
ticket = T.add_element("image", src=ASSETS["0_element_4"], x=100, y=900, w=200, h=100)

# 4. Final Adjustments
# Ensure layout is balanced
T.align_elements([headline, date_text, details], align_x="left")

# Add a subtle separator line
separator = T.add_element("image", src=ASSETS["5_element_6"], x=100, y=520, w=400, h=5)
T.update_style(separator, opacity=0.5)

# Group elements for organization (optional but good practice)
content_group = T.group_elements([headline, date_text, details, separator, ticket])
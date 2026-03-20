# Set background color for the canvas - opting for a slightly deeper, more cinematic navy
T.layout["background"] = "#0f2038"

# 1. Background Elements
# Subtle texture/gradient or decorative shapes to add depth without clutter
# Using the accent strip but moving it to the background as a subtle frame, not an overlay
bg_accent = T.add_element("image", src=ASSETS["5_element_0"], x=0, y=0, w=1920, h=1080)
T.update_style(bg_accent, opacity=0.05)

# 2. Main Illustration
# Positioning the sofa graphic, giving it space on the right side
hero_illustration = T.add_element("image", src=ASSETS["0_element_1"], x=750, y=300, w=1000, h=650)

# 3. Text Elements
# Grouping text together for better hierarchy
# Using a clear, high-contrast palette: white for header, soft gold/yellow for subhead
headline = T.add_element(
    "text", 
    text="MOVIE NIGHT", 
    x=100, y=150, w=800, h=150,
    fontFamily="Bungee", 
    fontSize=120, 
    textFill="#ffffff", 
    align="left"
)

subheadline = T.add_element(
    "text", 
    text="FRIDAY, OCTOBER 27TH | 7:00 PM", 
    x=100, y=280, w=700, h=60,
    fontFamily="Bebas Neue", 
    fontSize=55, 
    textFill="#ffcc00", 
    align="left"
)

# A clean separator line
separator = T.add_element("image", src=ASSETS["5_element_6"], x=100, y=360, w=400, h=15)
T.update_style(separator, opacity=0.8)

body_text = T.add_element(
    "text", 
    text="Join us for an evening of classic films, popcorn, and good company.\n\nBring your favorite blanket and get cozy!\n\n123 Cinema Lane, Movie Town", 
    x=100, y=420, w=600, h=300,
    fontFamily="Quicksand", 
    fontSize=32, 
    textFill="#e0e0e0", 
    align="left",
    lineHeight=1.5
)

# 4. Decorative & Atmosphere Elements
# Use the ticket as a stylized graphic element near the bottom, not as a main content block
ticket = T.add_element("image", src=ASSETS["0_element_4"], x=100, y=750, w=300, h=150)
T.update_style(ticket, opacity=0.9)

# Scatter some stars around the illustration to fill negative space
star1 = T.add_element("image", src=ASSETS["4_element_27"], x=1500, y=100, w=120, h=120)
star2 = T.add_element("image", src=ASSETS["4_element_28"], x=1750, y=200, w=80, h=80)
star3 = T.add_element("image", src=ASSETS["4_element_27"], x=1300, y=50, w=60, h=60)
T.update_style([star1, star2, star3], opacity=0.6)

# 5. Final Alignment & Layering
# Ensure everything is neatly layered
T.reorder_layer(bg_accent, "back")
T.reorder_layer(hero_illustration, "backward")
T.reorder_layer([headline, subheadline, separator, body_text, ticket], "front")
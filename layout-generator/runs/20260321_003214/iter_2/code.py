# Set background color for the canvas
T.layout["background"] = "#1a4378"

# 1. Background elements
# A subtle vertical accent strip to frame the text area
accent_strip = T.add_element("image", src=ASSETS["5_element_0"], x=0, y=0, w=400, h=1080)
T.update_style(accent_strip, opacity=0.08)

# 2. Main Illustration
# Positioning the sofa graphic, giving it breathing room on the right
hero_illustration = T.add_element("image", src=ASSETS["0_element_1"], x=850, y=250, w=950, h=700)

# 3. Text Elements
# Grouping text together for better hierarchy and readability
headline = T.add_element(
    "text", 
    text="MOVIE NIGHT", 
    x=100, y=200, w=700, h=150,
    fontFamily="Bungee", 
    fontSize=110, 
    textFill="#ffffff", 
    align="left"
)

subheadline = T.add_element(
    "text", 
    text="FRIDAY, OCTOBER 27TH | 7:00 PM", 
    x=100, y=340, w=700, h=80,
    fontFamily="Bebas Neue", 
    fontSize=50, 
    textFill="#ffdf00", 
    align="left"
)

# Decorative line to separate header from body
separator = T.add_element("image", src=ASSETS["5_element_6"], x=100, y=420, w=300, h=10)
T.update_style(separator, opacity=0.6)

body_text = T.add_element(
    "text", 
    text="Join us for an evening of classic films, popcorn, and good company.\n\nBring your favorite blanket and get cozy!\n\n123 Cinema Lane, Movie Town", 
    x=100, y=480, w=600, h=300,
    fontFamily="Quicksand", 
    fontSize=28, 
    textFill="#ffffff", 
    align="left",
    lineHeight=1.6
)

# 4. Decorative Elements
# Integrating the ticket graphic as a stylized footer or badge
ticket = T.add_element("image", src=ASSETS["0_element_4"], x=100, y=850, w=250, h=120)

# Adding stars to create a cinematic atmosphere
star1 = T.add_element("image", src=ASSETS["4_element_27"], x=600, y=100, w=150, h=150)
star2 = T.add_element("image", src=ASSETS["4_element_28"], x=1600, y=150, w=100, h=100)
T.update_style([star1, star2], opacity=0.8)

# 5. Final Alignment & Layering
# Ensure the text block is clean
T.align_elements([headline, subheadline, separator, body_text, ticket], align_x="left")
T.reorder_layer(accent_strip, "back")
T.reorder_layer(hero_illustration, "backward") # Keep illustration behind the text if they overlap
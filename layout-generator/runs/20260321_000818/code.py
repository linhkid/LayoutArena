# Reset canvas
T.layout["background"] = "#1d2c4e"

# 1. Background & Decorative Elements
# Add the frame first, then move it to the back
frame_id = T.add_element("svg", 50, 50, 1820, 980, src=ASSETS["2_element_1"])
T.reorder_layer(frame_id, "back")

# Add floating decorative elements to create depth
# Using ticket and stars to frame the content
ticket_top_left = T.add_element("svg", 100, 80, 150, 80, src=ASSETS["0_element_4"])
star_top_right = T.add_element("svg", 1750, 100, 80, 80, src=ASSETS["4_element_28"])
star_bottom_left = T.add_element("svg", 100, 900, 80, 80, src=ASSETS["4_element_27"])
ticket_bottom_right = T.add_element("svg", 1650, 850, 180, 100, src=ASSETS["0_element_4"])

# 2. Main Visual: Couch/Cinema Illustration
# Positioned to the right, balanced against text on the left
couch_id = T.add_element("svg", 900, 250, 850, 600, src=ASSETS["0_element_1"])

# 3. Text Content (Left-aligned, grouped logically)
# Headline
headline_id = T.add_element(
    "text", 150, 250, 700, 150, 
    text="MOVIE NIGHT", 
    fontFamily="Bebas Neue", 
    fontSize=140, 
    textFill="#ffdf00", 
    align="left"
)

# Subheadline
subhead_id = T.add_element(
    "text", 150, 400, 600, 80, 
    text="Grab your popcorn and join us!", 
    fontFamily="Quicksand", 
    fontSize=45, 
    textFill="#ffffff", 
    align="left"
)

# Event Details Container
# Using a clean rectangle panel behind the text for better readability
panel_id = T.add_element("svg", 130, 520, 650, 280, src=ASSETS["0_element_4"]) 
T.update_style([panel_id], opacity=0.1, fill="#ffffff") 

# Event details text
details_text = "FRIDAY, OCTOBER 20TH\n7:00 PM | THE BACKYARD CINEMA\n123 FILM STREET"
details_id = T.add_element(
    "text", 160, 560, 600, 220, 
    text=details_text, 
    fontFamily="Quicksand", 
    fontSize=36, 
    textFill="#ffffff", 
    align="left",
    lineHeight=1.8
)

# 4. Final Polish & Adjustments
# Ensure layers are correct for depth
T.reorder_layer(panel_id, "backward") 
T.reorder_layer(couch_id, "back") 

# Grouping text elements for cleaner management
text_group_id = T.group_elements([headline_id, subhead_id, panel_id, details_id])

# Final adjustments to layout
T.align_elements([couch_id], align_y="middle")
# Reset canvas
T.layout["background"] = "#1d2c4e"

# 1. Background & Decorative Elements
# Add the frame first, then move it to the back
frame_id = T.add_element("svg", 50, 50, 1820, 980, src=ASSETS["2_element_1"])
T.reorder_layer(frame_id, "back")

# Add floating decorative elements to create depth
# Using ticket and stars to frame the content
ticket_top_left = T.add_element("svg", 100, 100, 120, 60, src=ASSETS["0_element_4"])
star_top_right = T.add_element("svg", 1700, 80, 80, 80, src=ASSETS["4_element_28"])
star_bottom_left = T.add_element("svg", 150, 850, 100, 100, src=ASSETS["4_element_27"])
ticket_bottom_right = T.add_element("svg", 1600, 850, 150, 80, src=ASSETS["0_element_4"])

# 2. Main Visual: Couch/Cinema Illustration
# Positioned to the right, balanced against text on the left
couch_id = T.add_element("svg", 950, 250, 800, 600, src=ASSETS["0_element_1"])

# 3. Text Content (Left-aligned, grouped logically)
# Headline
headline_id = T.add_element(
    "text", 150, 300, 700, 150, 
    text="MOVIE NIGHT", 
    fontFamily="Bebas Neue", 
    fontSize=130, 
    textFill="#ffdf00", 
    align="left"
)

# Subheadline (add some spacing from headline)
subhead_id = T.add_element(
    "text", 150, 450, 600, 80, 
    text="Grab your popcorn and join us!", 
    fontFamily="Quicksand", 
    fontSize=40, 
    textFill="#ffffff", 
    align="left"
)

# Event Details (Grouped with a subtle background panel for readability)
# Adding a subtle panel behind text to separate it from the background
panel_id = T.add_element("svg", 130, 580, 650, 220, src=ASSETS["0_element_4"]) 
T.update_style([panel_id], opacity=0.15, fill="#ffffff") # Subtle overlay

details_text = "FRIDAY, OCTOBER 20TH\n7:00 PM | THE BACKYARD CINEMA\n123 FILM STREET"
details_id = T.add_element(
    "text", 150, 600, 600, 200, 
    text=details_text, 
    fontFamily="Quicksand", 
    fontSize=32, 
    textFill="#ffffff", 
    align="left",
    lineHeight=1.6
)

# Adjustments for better composition
T.reorder_layer(panel_id, "backward") # Ensure panel is behind text but above bg
T.reorder_layer(couch_id, "back") # Keep couch as a secondary element
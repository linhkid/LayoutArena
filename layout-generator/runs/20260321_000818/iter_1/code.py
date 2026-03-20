# Canvas setup
T.layout["background"] = "rgba(29, 44, 78, 1)"

# Add frame to create visual boundary
frame_id = T.add_element("svg", 50, 50, 1820, 980, src=ASSETS["2_element_1"])

# Add main visual: Couch illustration
couch_id = T.add_element("svg", 950, 250, 800, 600, src=ASSETS["0_element_1"])

# Add decorative elements (stars and tickets) to build a festive atmosphere
star1_id = T.add_element("svg", 150, 700, 150, 150, src=ASSETS["4_element_27"])
star2_id = T.add_element("svg", 1700, 150, 100, 100, src=ASSETS["4_element_28"])
ticket1_id = T.add_element("svg", 200, 200, 200, 100, src=ASSETS["0_element_4"])
ticket2_id = T.add_element("svg", 700, 800, 200, 100, src=ASSETS["0_element_4"])

# Add Text Content
# Headline
headline_id = T.add_element(
    "text", 200, 350, 700, 200, 
    text="MOVIE NIGHT", 
    fontFamily="Bebas Neue", 
    fontSize=140, 
    textFill="#ffdf00", 
    align="left"
)

# Subheadline
subhead_id = T.add_element(
    "text", 200, 500, 600, 100, 
    text="Grab your popcorn and join us!", 
    fontFamily="Quicksand", 
    fontSize=45, 
    textFill="#ffffff", 
    align="left"
)

# Event Details
details_id = T.add_element(
    "text", 200, 600, 600, 200, 
    text="FRIDAY, OCTOBER 20TH\n7:00 PM | THE BACKYARD CINEMA\n123 FILM STREET", 
    fontFamily="Quicksand", 
    fontSize=30, 
    textFill="#ffffff", 
    align="left",
    lineHeight=1.5
)

# Style tweaks: rotate some elements for a playful, dynamic look
T.resize_elements([star1_id], 200, 200)
T.reorder_layer(frame_id, "back")
T.reorder_layer(couch_id, "back")
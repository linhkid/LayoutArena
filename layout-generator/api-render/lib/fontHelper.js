const { logger } = require('./logger');

/**
 * Font mapping from font IDs to Google Fonts family names
 * Based on the FONT_MAP provided by the user
 */
const FONT_MAP = {
  0: "Arial",
  1: "Montserrat",
  2: "Bebas Neue",
  3: "Raleway",
  4: "Josefin Sans",
  5: "Cantarell",
  6: "Playfair Display",
  7: "Oswald",
  8: "Blogger Sans",
  9: "Abril Fatface",
  10: "Prompt",
  11: "Comfortaa",
  12: "Rubik",
  13: "Open Sans",
  14: "Roboto",
  15: "Libre Baskerville",
  16: "Quicksand",
  17: "Dosis",
  18: "Podkova",
  19: "Lato",
  20: "Cormorant Infant",
  21: "Amatic SC",
  22: "Fjalla One",
  23: "Playlist Script",
  24: "Arapey",
  25: "Baloo Tamma 2",
  26: "Graduate",
  27: "Titillium Web",
  28: "Kreon",
  29: "Nunito",
  30: "Rammetto One",
  31: "Anton",
  32: "Poiret One",
  33: "Alfa Slab One",
  34: "Play",
  35: "Righteous",
  36: "Space Mono",
  37: "Frank Ruhl Libre",
  38: "Yanone Kaffeesatz",
  39: "Pacifico",
  40: "Bangers",
  41: "Yellowtail",
  42: "Droid Serif",
  43: "Merriweather",
  44: "Racing Sans One",
  45: "Miriam Libre",
  46: "Crete Round",
  47: "Rubik One",
  48: "Bungee",
  49: "Sansita One",
  50: "Economica",
  51: "Patua One",
  52: "Caveat",
  53: "Philosopher",
  54: "Limelight",
  55: "Breathe",
  56: "Rokkitt",
  57: "Russo One",
  58: "Tinos",
  59: "Josefin Slab",
  60: "Oleo Script",
  61: "Arima Madurai",
  62: "Noticia Text",
  63: "Kalam",
  64: "Old Standard TT",
  65: "Playball",
  66: "Bad Script",
  67: "Six Caps",
  68: "Patrick Hand",
  69: "Orbitron",
  70: "Contrail One",
  71: "Selima Script",
  72: "El Messiri",
  73: "Bubbler One",
  74: "Gravitas One",
  75: "Italiana",
  76: "Pompiere",
  77: "Lemon Tuesday",
  78: "Vast Shadow",
  79: "Sunday",
  80: "Cookie",
  81: "Exo 2",
  82: "Barrio",
  83: "Brusher",
  84: "Radley",
  85: "Mrs Sheppards",
  86: "Grand Hotel",
  87: "Great Vibes",
  88: "Maven Pro",
  89: "Knewave",
  90: "Damion",
  91: "Tulpen One",
  92: "Parisienne",
  93: "Superclarendon",
  94: "Nixie One",
  95: "Permanent Marker",
  96: "Medula One",
  97: "Oxygen",
  98: "Vollkorn",
  99: "Cabin Sketch",
  100: "Yeseva One",
  101: "Montserrat Alternates",
  102: "Satisfy",
  103: "Sacramento",
  104: "Carter One",
  105: "Glass Antiqua",
  106: "Mr Dafoe",
  107: "Lauren",
  108: "Oranienbaum",
  109: "Scope One",
  110: "Mr De Haviland",
  111: "Pirou",
  112: "Rise",
  113: "Sensei",
  114: "Yesteryear",
  115: "Delius",
  116: "Copse",
  117: "Sue Ellen Francisco",
  118: "Monda",
  119: "Pattaya",
  120: "Dancing Script",
  121: "Reem Kufi",
  122: "Playlist",
  123: "Kaushan Script",
  124: "Beacon",
  125: "Reenie Beanie",
  126: "Overlock",
  127: "Mrs Saint Delafield",
  128: "Open Sans Condensed",
  129: "Covered By Your Grace",
  130: "Varela Round",
  131: "Allura",
  132: "Buda",
  133: "Brusher",
  134: "Nothing You Could Do",
  135: "Fredericka the Great",
  136: "Arkana",
  137: "Rochester",
  138: "Port Lligat Slab",
  139: "Arimo",
  140: "Dawning of a New Day",
  141: "Aldrich",
  142: "Mikodacs",
  143: "Neucha",
  144: "Heebo",
  145: "Source Serif Pro",
  146: "Shadows Into Light Two",
  147: "Armata",
  148: "Cutive Mono",
  149: "Merienda One",
  150: "Rissatypeface",
  151: "Stalemate",
  152: "Assistant",
  153: "Pathway Gothic One",
  154: "Breathe",
  155: "Suez One",
  156: "Berkshire Swash",
  157: "Rakkas",
  158: "Pinyon Script",
  159: "PT Sans",
  160: "Delius Swash Caps",
  161: "Offside",
  162: "Clicker Script",
  163: "Mate",
  164: "Kurale",
  165: "Rye",
  166: "Julius Sans One",
  167: "Lalezar",
  168: "Quattrocento",
  169: "VT323",
  170: "Bentham",
  171: "Finger Paint",
  172: "La Belle Aurore",
  173: "Press Start 2P",
  174: "Junge",
  175: "Iceberg",
  176: "Inconsolata",
  177: "Kelly Slab",
  178: "Handlee",
  179: "Rosario",
  180: "Gaegu",
  181: "Homemade Apple",
  182: "Londrina Shadow",
  183: "Meddon",
  184: "Gluk Foglihtenno06",
  185: "Elsie Swash Caps",
  186: "Share Tech Mono",
  187: "Black Ops One",
  188: "Fauna One",
  189: "Alice",
  190: "Arizonia",
  191: "Text Me One",
  192: "Nova Square",
  193: "Bungee Shade",
  194: "Just Me Again Down Here",
  195: "Jacques Francois Shadow",
  196: "Cousine",
  197: "Forum",
  198: "Architects Daughter",
  199: "Cedarville Cursive",
  200: "Elsie",
  201: "Sirin Stencil",
  202: "Vampiro One",
  203: "IM Fell DW Pica SC",
  204: "Dorsa",
  205: "Marcellus SC",
  206: "Kumar One",
  207: "Allerta Stencil",
  208: "Courgette",
  209: "Rationale",
  210: "Stint Ultra Expanded",
  211: "Happy Monkey",
  212: "Rock Salt",
  213: "Faster One",
  214: "Bellefair",
  215: "Wire One",
  216: "Geo",
  217: "Farsan",
  218: "Chathura",
  219: "Euphoria Script",
  220: "Zeyada",
  221: "Jura",
  222: "Loved by the King",
  223: "League Script",
  224: "Give You Glory",
  225: "Znikomitno24",
  226: "Alegreya Sans",
  227: "Kristi",
  228: "Knewave",
  229: "Pangolin",
  230: "Okolaks",
  231: "Seymour One",
  232: "Didact Gothic",
  233: "Kavivanar",
  234: "Underdog",
  235: "Alef",
  236: "Italianno",
  237: "Londrina Sketch",
  238: "Katibeh",
  239: "Caesar Dressing",
  240: "Lovers Quarrel",
  241: "Iceland",
  242: "Secular One",
  243: "Waiting for the Sunrise",
  244: "David Libre",
  245: "Marck Script",
  246: "Kumar One Outline",
  247: "Znikomit",
  248: "Monsieur La Doulaise",
  249: "Gruppo",
  250: "Monofett",
  251: "GFS Didot",
  252: "Petit Formal Script",
  253: "Constantine",
  254: "EB Garamond",
  255: "Ewert",
  256: "Bilbo",
  257: "Raleway Dots",
  258: "Gabriela",
  259: "Ruslan Display",
};

// Cache for Google Fonts CSS to font file URL mappings
const fontUrlCache = new Map();

/**
 * Normalizes font family name for Google Fonts API
 * @param {string} fontFamily - Font family name
 * @returns {string} Normalized font family name for URL
 */
function normalizeFontName(fontFamily) {
  if (!fontFamily) return '';
  return fontFamily.replace(/\s+/g, '+');
}

/**
 * Fetches Google Fonts CSS and extracts the actual font file URL
 * @param {string} fontFamily - Font family name
 * @param {string} weight - Font weight (e.g., '400', '700')
 * @param {string} style - Font style ('normal' or 'italic')
 * @returns {Promise<string>} URL to the font file
 */
async function fetchGoogleFontUrl(fontFamily, weight = '400', style = 'normal') {
  const cacheKey = `${fontFamily}|${weight}|${style}`;

  // Check cache first
  if (fontUrlCache.has(cacheKey)) {
    return fontUrlCache.get(cacheKey);
  }

  try {
    const normalizedFamily = normalizeFontName(fontFamily);
    const googleFontsApiUrl = `https://fonts.googleapis.com/css2?family=${normalizedFamily}:wght@${weight}&display=swap`;

    const response = await fetch(googleFontsApiUrl, {
      headers: {
        // Request font file format (woff2 is most modern and compressed)
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch Google Font CSS: ${response.status}`);
    }

    const cssText = await response.text();

    // Extract font URL from CSS
    // Format: src: url(https://fonts.gstatic.com/s/...) format('woff2');
    const urlMatch = cssText.match(/src:\s*url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/);

    if (!urlMatch || !urlMatch[1]) {
      throw new Error(`Could not extract font URL from CSS for ${fontFamily}`);
    }

    const fontUrl = urlMatch[1];

    // Cache the result
    fontUrlCache.set(cacheKey, fontUrl);

    logger.info('fontHelper.fetchGoogleFontUrl', {
      fontFamily,
      weight,
      style,
      fontUrl: fontUrl.substring(0, 80) + '...'
    });

    return fontUrl;
  } catch (error) {
    logger.error('fontHelper.fetchGoogleFontUrl', error, { fontFamily, weight, style });
    // Return null to indicate failure (caller can decide to skip or use fallback)
    return null;
  }
}

/**
 * Checks if a font family is a Google Font (exists in FONT_MAP or is a common Google Font)
 * @param {string} fontFamily - Font family name
 * @returns {boolean}
 */
function isGoogleFont(fontFamily) {
  if (!fontFamily) return false;

  // Check if it's in FONT_MAP
  const fontMapValues = Object.values(FONT_MAP);
  if (fontMapValues.some(f => f.toLowerCase() === fontFamily.toLowerCase())) {
    return true;
  }

  // System fonts that should not be fetched from Google Fonts
  const systemFonts = ['arial', 'helvetica', 'times new roman', 'times', 'courier', 'courier new', 'georgia', 'verdana'];
  return !systemFonts.includes(fontFamily.toLowerCase());
}

/**
 * Parses font weight from fontStyle string or returns default
 * @param {string} fontStyle - Font style string (may contain weight info like "bold")
 * @returns {string} Numeric weight (e.g., '400', '700')
 */
function parseFontWeight(fontStyle, fontWeight) {
  // If explicit fontWeight is provided
  if (fontWeight) {
    if (typeof fontWeight === 'number') return String(fontWeight);
    if (fontWeight === 'bold') return '700';
    if (fontWeight === 'normal') return '400';
    if (/^\d{3}$/.test(fontWeight)) return fontWeight;
  }

  // Parse from fontStyle string
  if (fontStyle) {
    if (fontStyle.includes('bold')) return '700';
    if (fontStyle.includes('light')) return '300';
  }

  return '400'; // Default regular weight
}

module.exports = {
  FONT_MAP,
  normalizeFontName,
  fetchGoogleFontUrl,
  isGoogleFont,
  parseFontWeight,
  fontUrlCache,
};

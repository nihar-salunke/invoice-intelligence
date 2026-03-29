"""Build the Invoice Intelligence hackathon pitch deck using Google Slides API."""
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_PATH = "/Users/nihar.salunke/.config/gws/slides_token.json"

creds = Credentials.from_authorized_user_file(TOKEN_PATH)
slides_service = build("slides", "v1", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

# --- Color constants (RGB 0-1) ---
WHITE = {"red": 1, "green": 1, "blue": 1}
DARK_BG = {"red": 0.11, "green": 0.11, "blue": 0.14}  # #1C1C24
ACCENT_BLUE = {"red": 0.24, "green": 0.47, "blue": 0.96}  # #3D78F5
ACCENT_GREEN = {"red": 0.18, "green": 0.80, "blue": 0.44}  # #2ECC71
ACCENT_RED = {"red": 0.91, "green": 0.30, "blue": 0.24}  # #E84D3D
ACCENT_ORANGE = {"red": 0.95, "green": 0.61, "blue": 0.07}  # #F39C12
LIGHT_GRAY = {"red": 0.75, "green": 0.75, "blue": 0.78}
MID_GRAY = {"red": 0.40, "green": 0.40, "blue": 0.44}
CARD_BG = {"red": 0.16, "green": 0.16, "blue": 0.20}  # #292933

EMU = 914400  # 1 inch in EMU
SLIDE_W = 10 * EMU
SLIDE_H = 5.625 * EMU  # 16:9


def emu(inches):
    return int(inches * EMU)


def pt(points):
    return {"magnitude": points, "unit": "PT"}


def rgb_color(color_dict):
    return {"rgbColor": color_dict}


# ---- Step 1: Create presentation ----
pres = slides_service.presentations().create(
    body={"title": "Invoice Intelligence — Hackathon Pitch Deck"}
).execute()
PRES_ID = pres["presentationId"]
print(f"Created presentation: https://docs.google.com/presentation/d/{PRES_ID}/edit")

# The first slide is auto-created; we'll track IDs
first_slide_id = pres["slides"][0]["objectId"]

# ---- Helper: generate unique IDs ----
_counter = 0
def uid(prefix="obj"):
    global _counter
    _counter += 1
    return f"{prefix}_{_counter}"


# ---- Build all requests ----
requests = []

# Delete the default first slide (we'll create our own)
requests.append({"deleteObject": {"objectId": first_slide_id}})


def add_slide(layout="BLANK"):
    sid = uid("slide")
    requests.append({
        "createSlide": {
            "objectId": sid,
            "slideLayoutReference": {"predefinedLayout": layout},
        }
    })
    return sid


def set_bg(slide_id, color):
    requests.append({
        "updatePageProperties": {
            "objectId": slide_id,
            "pageProperties": {
                "pageBackgroundFill": {
                    "solidFill": {"color": rgb_color(color)}
                }
            },
            "fields": "pageBackgroundFill",
        }
    })


def add_textbox(slide_id, left, top, width, height):
    eid = uid("txt")
    requests.append({
        "createShape": {
            "objectId": eid,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": width, "unit": "EMU"},
                         "height": {"magnitude": height, "unit": "EMU"}},
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": left, "translateY": top,
                    "unit": "EMU",
                },
            },
        }
    })
    return eid


def add_rect(slide_id, left, top, width, height, fill_color):
    eid = uid("rect")
    requests.append({
        "createShape": {
            "objectId": eid,
            "shapeType": "RECTANGLE",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": width, "unit": "EMU"},
                         "height": {"magnitude": height, "unit": "EMU"}},
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": left, "translateY": top,
                    "unit": "EMU",
                },
            },
        }
    })
    requests.append({
        "updateShapeProperties": {
            "objectId": eid,
            "shapeProperties": {
                "shapeBackgroundFill": {
                    "solidFill": {"color": rgb_color(fill_color)}
                },
                "outline": {"outlineFill": {"solidFill": {"color": rgb_color(fill_color)}}}
            },
            "fields": "shapeBackgroundFill,outline",
        }
    })
    return eid


def insert_text(element_id, text):
    requests.append({
        "insertText": {"objectId": element_id, "text": text, "insertionIndex": 0}
    })


def style_text(element_id, start, end, font_size, color, bold=False, font_family="Roboto"):
    style = {
        "fontSize": pt(font_size),
        "foregroundColor": {"opaqueColor": rgb_color(color)},
        "bold": bold,
        "fontFamily": font_family,
    }
    fields = "fontSize,foregroundColor,bold,fontFamily"
    requests.append({
        "updateTextStyle": {
            "objectId": element_id,
            "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end},
            "style": style,
            "fields": fields,
        }
    })


def style_paragraph(element_id, start, end, alignment="START"):
    requests.append({
        "updateParagraphStyle": {
            "objectId": element_id,
            "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end},
            "style": {"alignment": alignment},
            "fields": "alignment",
        }
    })


def add_styled_text(slide_id, left, top, width, height, text, font_size, color,
                     bold=False, alignment="START", font_family="Roboto"):
    eid = add_textbox(slide_id, left, top, width, height)
    insert_text(eid, text)
    style_text(eid, 0, len(text), font_size, color, bold, font_family)
    style_paragraph(eid, 0, len(text), alignment)
    return eid


# =============================================================================
# SLIDE 1: TITLE
# =============================================================================
s1 = add_slide()
set_bg(s1, DARK_BG)
# Accent line at top
add_rect(s1, 0, 0, SLIDE_W, emu(0.06), ACCENT_BLUE)

add_styled_text(s1, emu(1), emu(1.2), emu(8), emu(0.9),
                "Invoice Intelligence", 44, WHITE, bold=True, alignment="CENTER")

add_styled_text(s1, emu(1), emu(2.1), emu(8), emu(0.6),
                "Agentic AI for Tractor Invoice Verification", 24, ACCENT_BLUE,
                alignment="CENTER")

add_styled_text(s1, emu(1), emu(3.2), emu(8), emu(0.5),
                "5-agent pipeline  |  Gemini 2.5 Flash  |  Google Search grounding",
                14, LIGHT_GRAY, alignment="CENTER")

add_styled_text(s1, emu(1), emu(4.2), emu(8), emu(0.5),
                "IDFC FIRST Bank Hackathon 2026", 16, ACCENT_ORANGE, bold=True,
                alignment="CENTER")


# =============================================================================
# SLIDE 2: THE PROBLEM
# =============================================================================
s2 = add_slide()
set_bg(s2, DARK_BG)
add_rect(s2, 0, 0, SLIDE_W, emu(0.06), ACCENT_RED)

add_styled_text(s2, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "The Problem", 32, ACCENT_RED, bold=True)

add_styled_text(s2, emu(0.6), emu(1.0), emu(8.8), emu(0.5),
                "Manual invoice verification is slow, expensive, and error-prone",
                18, WHITE, bold=True)

bullets = (
    "\u2022  10 lakh tractors sold per year in India (FADA CY 2025)\n"
    "\u2022  ~7-8 lakh tractor loans requiring invoice verification\n"
    "\u2022  Each loan needs 2-3 documents manually reviewed\n"
    "\u2022  12 minutes per document \u2014 officers check dealer, specs, signatures\n"
    "\u2022  3-5% manual data entry error rate\n"
    "\u2022  7 in 10 loan applicants drop out due to slow processes (TransUnion)"
)
add_styled_text(s2, emu(0.6), emu(1.7), emu(5.5), emu(3.2),
                bullets, 14, LIGHT_GRAY)

# Stat boxes on right
box1 = add_rect(s2, emu(6.6), emu(1.7), emu(3.0), emu(1.0), CARD_BG)
add_styled_text(s2, emu(6.8), emu(1.8), emu(2.6), emu(0.5),
                "12 min / doc", 24, ACCENT_RED, bold=True, alignment="CENTER")
add_styled_text(s2, emu(6.8), emu(2.3), emu(2.6), emu(0.3),
                "manual review time", 11, LIGHT_GRAY, alignment="CENTER")

box2 = add_rect(s2, emu(6.6), emu(2.9), emu(3.0), emu(1.0), CARD_BG)
add_styled_text(s2, emu(6.8), emu(3.0), emu(2.6), emu(0.5),
                "70% drop-off", 24, ACCENT_RED, bold=True, alignment="CENTER")
add_styled_text(s2, emu(6.8), emu(3.5), emu(2.6), emu(0.3),
                "loan applicant abandonment", 11, LIGHT_GRAY, alignment="CENTER")

box3 = add_rect(s2, emu(6.6), emu(4.1), emu(3.0), emu(1.0), CARD_BG)
add_styled_text(s2, emu(6.8), emu(4.2), emu(2.6), emu(0.5),
                "50-60 officers", 24, ACCENT_RED, bold=True, alignment="CENTER")
add_styled_text(s2, emu(6.8), emu(4.7), emu(2.6), emu(0.3),
                "needed for 2L loans/year", 11, LIGHT_GRAY, alignment="CENTER")


# =============================================================================
# SLIDE 3: OUR SOLUTION
# =============================================================================
s3 = add_slide()
set_bg(s3, DARK_BG)
add_rect(s3, 0, 0, SLIDE_W, emu(0.06), ACCENT_GREEN)

add_styled_text(s3, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "The Solution: 5-Agent AI Pipeline", 32, ACCENT_GREEN, bold=True)

add_styled_text(s3, emu(0.6), emu(1.0), emu(8.8), emu(0.5),
                "Upload an invoice \u2192 get a verified authenticity score in 15-30 seconds",
                16, WHITE)

# Agent cards
agents = [
    ("1", "Intake", "OpenCV + Pillow", "Preprocess image\n5.8MB \u2192 0.3MB", ACCENT_BLUE),
    ("2", "Extraction", "Gemini 2.5 Flash", "Extract 9 fields\nin one API call", ACCENT_BLUE),
    ("3", "Research", "Gemini + Search", "Verify HP & dealer\nvia Google Search", ACCENT_GREEN),
    ("4", "Validation", "Python rules", "Cross-check fields\nagainst business rules", ACCENT_ORANGE),
    ("5", "Scoring", "Python scoring", "0-100 score\nPASS / REVIEW / FAIL", ACCENT_RED),
]

card_w = emu(1.72)
gap = emu(0.1)
start_x = emu(0.5)

for i, (num, name, tech, desc, color) in enumerate(agents):
    x = start_x + i * (card_w + gap)
    y = emu(1.8)

    # Card background
    add_rect(s3, x, y, card_w, emu(2.8), CARD_BG)
    # Color accent bar on top of card
    add_rect(s3, x, y, card_w, emu(0.08), color)

    # Number circle area
    add_styled_text(s3, x, y + emu(0.15), card_w, emu(0.5),
                    f"Agent {num}", 13, color, bold=True, alignment="CENTER")

    add_styled_text(s3, x, y + emu(0.6), card_w, emu(0.4),
                    name, 16, WHITE, bold=True, alignment="CENTER")

    add_styled_text(s3, x, y + emu(1.05), card_w, emu(0.3),
                    tech, 10, ACCENT_BLUE, alignment="CENTER")

    add_styled_text(s3, x + emu(0.1), y + emu(1.5), card_w - emu(0.2), emu(1.0),
                    desc, 11, LIGHT_GRAY, alignment="CENTER")

# Arrow indicators between cards
for i in range(4):
    x = start_x + (i + 1) * (card_w + gap) - gap
    add_styled_text(s3, x - emu(0.1), emu(3.0), emu(0.3), emu(0.4),
                    "\u2192", 18, MID_GRAY, alignment="CENTER")

add_styled_text(s3, emu(0.6), emu(4.9), emu(8.8), emu(0.3),
                "Only 2 AI calls per document  \u2022  Shared context dict  \u2022  Full audit trail logged per agent",
                11, MID_GRAY, alignment="CENTER")


# =============================================================================
# SLIDE 4: HOW IT WORKS (key differentiators)
# =============================================================================
s4 = add_slide()
set_bg(s4, DARK_BG)
add_rect(s4, 0, 0, SLIDE_W, emu(0.06), ACCENT_BLUE)

add_styled_text(s4, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Key Capabilities", 32, ACCENT_BLUE, bold=True)

# Left column - Extraction
add_rect(s4, emu(0.5), emu(1.1), emu(4.3), emu(2.0), CARD_BG)
add_styled_text(s4, emu(0.7), emu(1.2), emu(3.9), emu(0.4),
                "Multimodal Extraction", 18, ACCENT_BLUE, bold=True)
extract_text = (
    "Single Gemini call extracts 9 fields:\n"
    "dealer name, model, HP, cost, signature,\n"
    "stamp, language, state, document type\n\n"
    "Handles Hindi, Marathi, regional invoices\n"
    "Auto-retries on malformed JSON"
)
add_styled_text(s4, emu(0.7), emu(1.7), emu(3.9), emu(1.3),
                extract_text, 12, LIGHT_GRAY)

# Right column - Research
add_rect(s4, emu(5.2), emu(1.1), emu(4.3), emu(2.0), CARD_BG)
add_styled_text(s4, emu(5.4), emu(1.2), emu(3.9), emu(0.4),
                "Web-Grounded Research", 18, ACCENT_GREEN, bold=True)
research_text = (
    "Google Search grounding verifies:\n"
    "\u2022  Is the tractor HP correct for this model?\n"
    "\u2022  Is the dealer a real, registered business?\n\n"
    "Catches fake dealers, inflated specs,\n"
    "and price manipulation automatically"
)
add_styled_text(s4, emu(5.4), emu(1.7), emu(3.9), emu(1.3),
                research_text, 12, LIGHT_GRAY)

# Bottom row
add_rect(s4, emu(0.5), emu(3.3), emu(4.3), emu(1.8), CARD_BG)
add_styled_text(s4, emu(0.7), emu(3.4), emu(3.9), emu(0.4),
                "Weighted Scoring (0-100)", 18, ACCENT_ORANGE, bold=True)
scoring_text = (
    "Field completeness     20 pts\n"
    "HP verification          20 pts\n"
    "Dealer verification     20 pts\n"
    "Signature present       15 pts\n"
    "Stamp present            15 pts\n"
    "Document quality        10 pts"
)
add_styled_text(s4, emu(0.7), emu(3.9), emu(3.9), emu(1.1),
                scoring_text, 11, LIGHT_GRAY, font_family="Roboto Mono")

add_rect(s4, emu(5.2), emu(3.3), emu(4.3), emu(1.8), CARD_BG)
add_styled_text(s4, emu(5.4), emu(3.4), emu(3.9), emu(0.4),
                "Compliance & Audit Trail", 18, WHITE, bold=True)
audit_text = (
    "Every agent logs: name, status, time, decision\n\n"
    "\u2022  Full traceability for RBI audits\n"
    "\u2022  Automated compliance reporting\n"
    "\u2022  PASS (\u226570) / REVIEW (40-69) / FAIL (<40)\n"
    "\u2022  Human review only for flagged invoices"
)
add_styled_text(s4, emu(5.4), emu(3.9), emu(3.9), emu(1.1),
                audit_text, 12, LIGHT_GRAY)


# =============================================================================
# SLIDE 5: BEFORE vs AFTER
# =============================================================================
s5 = add_slide()
set_bg(s5, DARK_BG)
add_rect(s5, 0, 0, SLIDE_W, emu(0.06), ACCENT_GREEN)

add_styled_text(s5, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Before vs After", 32, WHITE, bold=True)

# Before column
add_rect(s5, emu(0.5), emu(1.1), emu(4.3), emu(4.0), CARD_BG)
add_styled_text(s5, emu(0.7), emu(1.2), emu(3.9), emu(0.4),
                "Manual Process", 20, ACCENT_RED, bold=True)

before_items = [
    ("12 min", "per document"),
    ("50-60 officers", "for 2L loans/year"),
    ("INR 1.65 Cr", "annual staffing cost"),
    ("3-5%", "error rate"),
    ("1-3 days", "verification time"),
    ("7-10 days", "end-to-end loan processing"),
]
y_pos = emu(1.8)
for val, label in before_items:
    add_styled_text(s5, emu(0.7), y_pos, emu(2.0), emu(0.3),
                    val, 16, ACCENT_RED, bold=True)
    add_styled_text(s5, emu(2.7), y_pos + emu(0.03), emu(2.0), emu(0.3),
                    label, 12, LIGHT_GRAY)
    y_pos += emu(0.5)

# After column
add_rect(s5, emu(5.2), emu(1.1), emu(4.3), emu(4.0), CARD_BG)
add_styled_text(s5, emu(5.4), emu(1.2), emu(3.9), emu(0.4),
                "AI Pipeline", 20, ACCENT_GREEN, bold=True)

after_items = [
    ("15-30 sec", "per document"),
    ("~0 officers", "for automated docs"),
    ("INR 12.5L", "annual API + infra cost"),
    ("<2%", "error rate"),
    ("Real-time", "verification"),
    ("3-5 days", "end-to-end loan processing"),
]
y_pos = emu(1.8)
for val, label in after_items:
    add_styled_text(s5, emu(5.4), y_pos, emu(2.0), emu(0.3),
                    val, 16, ACCENT_GREEN, bold=True)
    add_styled_text(s5, emu(7.4), y_pos + emu(0.03), emu(2.0), emu(0.3),
                    label, 12, LIGHT_GRAY)
    y_pos += emu(0.5)

# Center arrow
add_styled_text(s5, emu(4.5), emu(2.8), emu(1.0), emu(0.6),
                "\u2192", 36, ACCENT_GREEN, alignment="CENTER")


# =============================================================================
# SLIDE 6: BUSINESS IMPACT (numbers)
# =============================================================================
s6 = add_slide()
set_bg(s6, DARK_BG)
add_rect(s6, 0, 0, SLIDE_W, emu(0.06), ACCENT_GREEN)

add_styled_text(s6, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Business Impact", 32, WHITE, bold=True)

add_styled_text(s6, emu(0.6), emu(0.85), emu(8.8), emu(0.3),
                "Estimated annual impact for a single large tractor-lending bank (2L loans/year)",
                13, MID_GRAY)

# Big number cards
impact_cards = [
    ("INR 1.5 Cr", "Cost Savings", "92% reduction in\nverification staffing", ACCENT_GREEN),
    ("INR 18 Cr", "Revenue Uplift", "Faster processing recovers\n5% of drop-off applicants", ACCENT_BLUE),
    ("INR 3.6 Cr", "Fraud Prevention", "Web verification catches\nfake dealers & inflated specs", ACCENT_ORANGE),
]

card_w_impact = emu(2.9)
for i, (number, title, desc, color) in enumerate(impact_cards):
    x = emu(0.5) + i * (card_w_impact + emu(0.15))
    y = emu(1.4)

    add_rect(s6, x, y, card_w_impact, emu(2.4), CARD_BG)
    add_rect(s6, x, y, card_w_impact, emu(0.08), color)

    add_styled_text(s6, x, y + emu(0.3), card_w_impact, emu(0.6),
                    number, 32, color, bold=True, alignment="CENTER")
    add_styled_text(s6, x, y + emu(0.9), card_w_impact, emu(0.4),
                    title, 16, WHITE, bold=True, alignment="CENTER")
    add_styled_text(s6, x, y + emu(1.4), card_w_impact, emu(0.8),
                    desc, 12, LIGHT_GRAY, alignment="CENTER")

# Total bar at bottom
add_rect(s6, emu(0.5), emu(4.1), emu(9.0), emu(0.9), ACCENT_BLUE)
add_styled_text(s6, emu(0.5), emu(4.2), emu(9.0), emu(0.5),
                "Total Quantifiable Impact: INR 23+ Cr / year",
                24, WHITE, bold=True, alignment="CENTER")
add_styled_text(s6, emu(0.5), emu(4.65), emu(9.0), emu(0.3),
                "per bank  \u2022  scales linearly with loan volume",
                12, WHITE, alignment="CENTER")


# =============================================================================
# SLIDE 7: COST ECONOMICS
# =============================================================================
s7 = add_slide()
set_bg(s7, DARK_BG)
add_rect(s7, 0, 0, SLIDE_W, emu(0.06), ACCENT_BLUE)

add_styled_text(s7, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Cost Economics: INR 0.25 per Document", 28, ACCENT_BLUE, bold=True)

# API cost breakdown
add_rect(s7, emu(0.5), emu(1.1), emu(4.3), emu(2.5), CARD_BG)
add_styled_text(s7, emu(0.7), emu(1.2), emu(3.9), emu(0.4),
                "Per-Document API Cost", 16, WHITE, bold=True)

cost_text = (
    "Gemini 2.5 Flash (Vertex AI):\n\n"
    "Image input (1,290 tokens)      $0.0004\n"
    "Prompt text (500 tokens)          $0.0002\n"
    "Output (800 tokens)                  $0.0020\n"
    "Per call total                              $0.0026\n\n"
    "x2 calls/doc = $0.005 = INR 0.42"
)
add_styled_text(s7, emu(0.7), emu(1.7), emu(3.9), emu(1.8),
                cost_text, 11, LIGHT_GRAY, font_family="Roboto Mono")

# Annual comparison
add_rect(s7, emu(5.2), emu(1.1), emu(4.3), emu(2.5), CARD_BG)
add_styled_text(s7, emu(5.4), emu(1.2), emu(3.9), emu(0.4),
                "Annual Cost Comparison", 16, WHITE, bold=True)

comparison_text = (
    "Manual process:\n"
    "  55 officers x INR 3L = INR 1.65 Cr\n\n"
    "AI pipeline:\n"
    "  5L docs x INR 0.25 + infra = INR 12.5L\n\n"
)
add_styled_text(s7, emu(5.4), emu(1.7), emu(3.9), emu(1.2),
                comparison_text, 13, LIGHT_GRAY)

add_styled_text(s7, emu(5.4), emu(2.9), emu(3.9), emu(0.4),
                "92% cost reduction", 20, ACCENT_GREEN, bold=True)

# Time savings
add_rect(s7, emu(0.5), emu(3.8), emu(9.0), emu(1.3), CARD_BG)
add_styled_text(s7, emu(0.7), emu(3.9), emu(4.0), emu(0.4),
                "Time Savings", 16, WHITE, bold=True)
time_text = (
    "Manual:  12 min/doc x 5L docs = 1,00,000 hours/year\n"
    "AI:          0.5 min/doc x 5L docs = 4,167 hours/year\n"
    "Saved:   95,833 hours/year (97% reduction)"
)
add_styled_text(s7, emu(0.7), emu(4.3), emu(8.5), emu(0.7),
                time_text, 12, LIGHT_GRAY, font_family="Roboto Mono")


# =============================================================================
# SLIDE 8: FRAUD DETECTION
# =============================================================================
s8 = add_slide()
set_bg(s8, DARK_BG)
add_rect(s8, 0, 0, SLIDE_W, emu(0.06), ACCENT_ORANGE)

add_styled_text(s8, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Fraud & Discrepancy Detection", 32, ACCENT_ORANGE, bold=True)

add_styled_text(s8, emu(0.6), emu(0.9), emu(8.8), emu(0.4),
                "The Research Agent cross-references every invoice against the open web",
                15, WHITE)

fraud_types = [
    ("Fake Dealers", "Dealer name not found in any\nonline business listing", "\U0001F6AB"),
    ("Inflated Specs", "Invoice claims 60 HP but\nmodel is actually 42 HP", "\u26A0\uFE0F"),
    ("Price Manipulation", "Cost significantly above\nmarket rate for the model", "\U0001F4B0"),
]

for i, (title, desc, icon) in enumerate(fraud_types):
    x = emu(0.5) + i * (emu(3.0) + emu(0.15))
    add_rect(s8, x, emu(1.5), emu(3.0), emu(1.8), CARD_BG)
    add_styled_text(s8, x, emu(1.6), emu(3.0), emu(0.4),
                    title, 18, ACCENT_ORANGE, bold=True, alignment="CENTER")
    add_styled_text(s8, x, emu(2.1), emu(3.0), emu(1.0),
                    desc, 13, LIGHT_GRAY, alignment="CENTER")

# Precedent box
add_rect(s8, emu(0.5), emu(3.6), emu(9.0), emu(1.4), CARD_BG)
add_styled_text(s8, emu(0.7), emu(3.7), emu(8.5), emu(0.4),
                "Real-World Precedent", 16, WHITE, bold=True)
precedent_text = (
    "Mahindra Finance detected INR 150 Cr fraud in retail vehicle loans (FY24)\n"
    "due to KYC document forgery.\n\n"
    "Conservative estimate: 2L loans x 0.3% fraud rate x INR 6L avg = INR 3.6 Cr prevented"
)
add_styled_text(s8, emu(0.7), emu(4.1), emu(8.5), emu(0.8),
                precedent_text, 13, LIGHT_GRAY)


# =============================================================================
# SLIDE 9: TECH STACK
# =============================================================================
s9 = add_slide()
set_bg(s9, DARK_BG)
add_rect(s9, 0, 0, SLIDE_W, emu(0.06), ACCENT_BLUE)

add_styled_text(s9, emu(0.6), emu(0.3), emu(8.8), emu(0.6),
                "Technology Stack", 32, ACCENT_BLUE, bold=True)

add_styled_text(s9, emu(0.6), emu(0.85), emu(8.8), emu(0.3),
                "Built entirely on Google Cloud + open-source", 14, MID_GRAY)

tech_items = [
    ("AI Model", "Gemini 2.5 Flash on Vertex AI", "Multimodal vision + text; 2 calls per doc"),
    ("Web Search", "Google Search Grounding", "Built into Gemini; verifies HP & dealer legitimacy"),
    ("Backend", "Python, FastAPI, OpenCV, Pillow", "Image preprocessing + REST API + agent orchestration"),
    ("Frontend", "React, Vite", "Upload UI, report cards, agent trail visualization"),
    ("Auth", "GCP Service Account (OAuth2)", "Secure Vertex AI access with minimal permissions"),
    ("Infra", "Stateless, single-server", "No database needed; JSON results per invoice"),
]

for i, (category, tech, desc) in enumerate(tech_items):
    y = emu(1.3) + i * emu(0.65)
    add_rect(s9, emu(0.5), y, emu(9.0), emu(0.55), CARD_BG)
    add_styled_text(s9, emu(0.7), y + emu(0.05), emu(1.8), emu(0.25),
                    category, 12, ACCENT_BLUE, bold=True)
    add_styled_text(s9, emu(2.6), y + emu(0.05), emu(3.0), emu(0.25),
                    tech, 12, WHITE, bold=True)
    add_styled_text(s9, emu(2.6), y + emu(0.28), emu(6.5), emu(0.25),
                    desc, 10, MID_GRAY)


# =============================================================================
# SLIDE 10: THANK YOU / CTA
# =============================================================================
s10 = add_slide()
set_bg(s10, DARK_BG)
add_rect(s10, 0, 0, SLIDE_W, emu(0.06), ACCENT_BLUE)

add_styled_text(s10, emu(1), emu(1.0), emu(8), emu(0.8),
                "Invoice Intelligence", 40, WHITE, bold=True, alignment="CENTER")

add_styled_text(s10, emu(1), emu(1.8), emu(8), emu(0.5),
                "INR 23+ Cr annual impact per bank", 22, ACCENT_GREEN, bold=True,
                alignment="CENTER")

add_styled_text(s10, emu(1), emu(2.7), emu(8), emu(0.5),
                "92% cost reduction  \u2022  97% faster  \u2022  <2% error rate",
                16, LIGHT_GRAY, alignment="CENTER")

add_styled_text(s10, emu(1), emu(3.5), emu(8), emu(0.4),
                "github.com/nihar-salunke/invoice-intelligence",
                14, ACCENT_BLUE, alignment="CENTER")

add_styled_text(s10, emu(1), emu(4.3), emu(8), emu(0.5),
                "Thank You", 28, ACCENT_ORANGE, bold=True, alignment="CENTER")


# ---- Execute all requests ----
print(f"\nSending {len(requests)} API requests...")

# Batch in chunks (API limit is 1000 requests per call)
CHUNK = 500
for i in range(0, len(requests), CHUNK):
    chunk = requests[i:i+CHUNK]
    slides_service.presentations().batchUpdate(
        presentationId=PRES_ID,
        body={"requests": chunk},
    ).execute()
    print(f"  Sent requests {i+1}-{min(i+CHUNK, len(requests))}")

print(f"\nDone! Open your deck:")
print(f"https://docs.google.com/presentation/d/{PRES_ID}/edit")

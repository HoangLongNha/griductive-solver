// Centralized Asset Manifest — Griductive (Hand-Painted 2D Mystery Adventure)
// Matches docs/art-direction/ART_BIBLE.md & PROJECT_AUDIT.md

window.GRIDUCTIVE_ASSETS = {
  palette: {
    warmCream: "#E8DCC3",
    agedPaper: "#D3C1A1",
    warmBeige: "#B9A58B",
    mutedTerracotta: "#A66D53",
    darkWalnut: "#49352F",
    dustyNavy: "#39465B",
    deepBlue: "#27344C",
    mutedOlive: "#77775C",
    charcoal: "#343333",
    warmHighlight: "#E6CFA0",
  },
  ui: {
    stampCriminal: { id: "ui-stamp-criminal", path: "/assets/ui/stamp_criminal.svg", format: "svg", status: "ready" },
    stampInnocent: { id: "ui-stamp-innocent", path: "/assets/ui/stamp_innocent.svg", format: "svg", status: "ready" },
    pinBrass: { id: "ui-pin-brass", path: "/assets/ui/pin_brass.svg", format: "svg", status: "ready" },
    rotaryPhone: { id: "ui-rotary-phone", path: "/assets/ui/rotary-phone.webp", format: "webp", status: "ready" },
    fortuneTeller: { id: "ui-fortune-teller", path: "/assets/ui/fortune-teller/portrait.webp", format: "webp", status: "ready" },
  },
  environments: {
    detectiveOffice: {
      background: { path: "/assets/environments/detective-office/background.webp", format: "webp", status: "ready" },
      midground: { path: "/assets/environments/detective-office/midground.webp", format: "webp", status: "ready" },
      foreground: { path: "/assets/environments/detective-office/foreground.webp", format: "webp", status: "ready" },
    },
  },
  // 25 Character Slots (16 defined in puzzles/ + 9 reserved 5x5 slots)
  characters: [
    { id: "char_01", name: "Alice", profession: "Detective", path: "/assets/characters/char_01/portrait.webp", format: "webp", status: "ready" },
    { id: "char_02", name: "Bao", profession: "Guard", path: "/assets/characters/char_02/portrait.webp", format: "webp", status: "ready" },
    { id: "char_03", name: "Chi", profession: "Artist", path: "/assets/characters/char_03/portrait.webp", format: "webp", status: "ready" },
    { id: "char_04", name: "Dung", profession: "Engineer", path: "/assets/characters/char_04/portrait.webp", format: "webp", status: "ready" },
    { id: "char_05", name: "Emi", profession: "Clerk", path: "/assets/characters/char_05/portrait.webp", format: "webp", status: "ready" },
    { id: "char_06", name: "Finn", profession: "Doctor", path: "/assets/characters/char_06/portrait.webp", format: "webp", status: "ready" },
    { id: "char_07", name: "Gia", profession: "Teacher", path: "/assets/characters/char_07/portrait.webp", format: "webp", status: "ready" },
    { id: "char_08", name: "Hanh", profession: "Farmer", path: "/assets/characters/char_08/portrait.webp", format: "webp", status: "ready" },
    { id: "char_09", name: "Ivy", profession: "Writer", path: "/assets/characters/char_09/portrait.webp", format: "webp", status: "ready" },
    { id: "char_10", name: "Jun", profession: "Student", path: "/assets/characters/char_10/portrait.webp", format: "webp", status: "ready" },
    { id: "char_11", name: "Khai", profession: "Pilot", path: "/assets/characters/char_11/portrait.webp", format: "webp", status: "ready" },
    { id: "char_12", name: "Linh", profession: "Chef", path: "/assets/characters/char_12/portrait.webp", format: "webp", status: "ready" },
    { id: "char_13", name: "Mai", profession: "Nurse", path: "/assets/characters/char_13/portrait.webp", format: "webp", status: "ready" },
    { id: "char_14", name: "Nam", profession: "Designer", path: "/assets/characters/char_14/portrait.webp", format: "webp", status: "ready" },
    { id: "char_15", name: "Oanh", profession: "Driver", path: "/assets/characters/char_15/portrait.webp", format: "webp", status: "ready" },
    { id: "char_16", name: "Phuc", profession: "Librarian", path: "/assets/characters/char_16/portrait.webp", format: "webp", status: "ready" },
    { id: "char_17", name: "Reserved-17", profession: "Mechanic", path: "/assets/characters/char_17/portrait.webp", format: "webp", status: "ready" },
    { id: "char_18", name: "Reserved-18", profession: "Journalist", path: "/assets/characters/char_18/portrait.webp", format: "webp", status: "ready" },
    { id: "char_19", name: "Reserved-19", profession: "Botanist", path: "/assets/characters/char_19/portrait.webp", format: "webp", status: "ready" },
    { id: "char_20", name: "Reserved-20", profession: "Musician", path: "/assets/characters/char_20/portrait.webp", format: "webp", status: "ready" },
    { id: "char_21", name: "Reserved-21", profession: "Tailor", path: "/assets/characters/char_21/portrait.webp", format: "webp", status: "ready" },
    { id: "char_22", name: "Reserved-22", profession: "Locksmith", path: "/assets/characters/char_22/portrait.webp", format: "webp", status: "ready" },
    { id: "char_23", name: "Reserved-23", profession: "Astronomer", path: "/assets/characters/char_23/portrait.webp", format: "webp", status: "ready" },
    { id: "char_24", name: "Reserved-24", profession: "Antique Dealer", path: "/assets/characters/char_24/portrait.webp", format: "webp", status: "ready" },
    { id: "char_25", name: "Reserved-25", profession: "Socialite", path: "/assets/characters/char_25/portrait.webp", format: "webp", status: "ready" },
  ],
};

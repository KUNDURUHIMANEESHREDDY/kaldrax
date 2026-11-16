import type {
  Allocation,
  AppState,
  Category,
  Item,
  MaterialRequest,
  Priority,
  Project,
  RequestStatus,
  Supplier,
  Transaction,
  TransactionType,
} from "./types";

/* ------------------------------------------------------------------ */
/* Time helpers                                                        */
/* ------------------------------------------------------------------ */

const NOW = new Date();

function daysAgo(n: number, hour = 10, minute = 0): string {
  const d = new Date(NOW);
  d.setDate(d.getDate() - n);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

function inDays(n: number, hour = 17): string {
  const d = new Date(NOW);
  d.setDate(d.getDate() + n);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

/* ------------------------------------------------------------------ */
/* Categories                                                          */
/* ------------------------------------------------------------------ */

export const seedCategories: Category[] = [
  {
    id: "CAT-01",
    name: "Boards & Microcontrollers",
    description: "Development boards, SBCs and programmable controllers",
    color: "#556b4f",
    icon: "chip",
  },
  {
    id: "CAT-02",
    name: "Sensors & Modules",
    description: "Environmental, motion, distance and vision modules",
    color: "#5c7c8a",
    icon: "activity",
  },
  {
    id: "CAT-03",
    name: "Electronic Components",
    description: "Discrete parts, drivers, displays and prototyping supplies",
    color: "#a67c52",
    icon: "circuit",
  },
  {
    id: "CAT-04",
    name: "Power & Batteries",
    description: "Cells, adapters, solar panels and charging modules",
    color: "#b39245",
    icon: "battery",
  },
  {
    id: "CAT-05",
    name: "Mechanical & Hardware",
    description: "Motors, fasteners, bearings and structural parts",
    color: "#7a7f87",
    icon: "cog",
  },
  {
    id: "CAT-06",
    name: "Tools & Equipment",
    description: "Bench instruments and shared lab tooling",
    color: "#6e7f6a",
    icon: "wrench",
  },
  {
    id: "CAT-07",
    name: "Fabrication Materials",
    description: "Sheets, filaments and stock for prototyping",
    color: "#8d7f6a",
    icon: "layers",
  },
  {
    id: "CAT-08",
    name: "Safety & Consumables",
    description: "PPE, cleaning supplies and first-aid stock",
    color: "#9c6b62",
    icon: "shield",
  },
];

/* ------------------------------------------------------------------ */
/* Suppliers                                                           */
/* ------------------------------------------------------------------ */

export const seedSuppliers: Supplier[] = [
  {
    id: "SUP-01",
    name: "Robu.in",
    contactName: "Nikhil Shetty",
    email: "nikhil@robu.in",
    phone: "+91 98604 22118",
    city: "Pune",
    leadTimeDays: 4,
    rating: 4.7,
    categoryIds: ["CAT-01", "CAT-02", "CAT-04"],
    onTimePct: 96,
    notes: "Preferred vendor for boards and sensor modules. Consolidated weekly PO.",
  },
  {
    id: "SUP-02",
    name: "ThinkRobotics",
    contactName: "Priya Nair",
    email: "priya@thinkrobotics.in",
    phone: "+91 80471 90233",
    city: "Bengaluru",
    leadTimeDays: 5,
    rating: 4.5,
    categoryIds: ["CAT-03", "CAT-05"],
    onTimePct: 91,
    notes: "Servos and drive train parts. Ships in 5 working days.",
  },
  {
    id: "SUP-03",
    name: "Element14 India",
    contactName: "Rahul Desai",
    email: "rahul.desai@element14.in",
    phone: "+91 22674 88100",
    city: "Mumbai",
    leadTimeDays: 8,
    rating: 4.3,
    categoryIds: ["CAT-02", "CAT-03", "CAT-08"],
    onTimePct: 88,
    notes: "Authorised distributor. Best for small SMD reels and PPE.",
  },
  {
    id: "SUP-04",
    name: "Mouser Electronics",
    contactName: "Sandra Lee",
    email: "sandra.lee@mouser.in",
    phone: "+91 80670 11442",
    city: "Bengaluru",
    leadTimeDays: 12,
    rating: 4.6,
    categoryIds: ["CAT-01", "CAT-06"],
    onTimePct: 84,
    notes: "Long lead time but reliable for STM32 and bench instruments.",
  },
  {
    id: "SUP-05",
    name: "FabLab Supplies Co.",
    contactName: "Aditya Kulkarni",
    email: "aditya@fablabsupplies.in",
    phone: "+91 40271 55890",
    city: "Hyderabad",
    leadTimeDays: 6,
    rating: 4.1,
    categoryIds: ["CAT-07"],
    onTimePct: 82,
    notes: "Filament, acrylic and MDF. Delivers on the Tuesday run.",
  },
  {
    id: "SUP-06",
    name: "Campus Hardware Depot",
    contactName: "Mahesh Pawar",
    email: "mahesh@campushardware.in",
    phone: "+91 98220 31104",
    city: "On campus",
    leadTimeDays: 2,
    rating: 3.9,
    categoryIds: ["CAT-05", "CAT-08"],
    onTimePct: 94,
    notes: "Walk-in store beside the workshop. Same-day pickup with indent.",
  },
];

/* ------------------------------------------------------------------ */
/* Items                                                               */
/* ------------------------------------------------------------------ */

type ItemSeed = {
  id: string;
  name: string;
  categoryId: string;
  description: string;
  qty: number;
  minQty: number;
  unit: string;
  location: string;
  supplierId: string;
  unitCost: number;
  createdDaysAgo: number;
};

const itemSeeds: ItemSeed[] = [
  {
    id: "ITM-1001",
    name: "Arduino Uno R3",
    categoryId: "CAT-01",
    description:
      "ATmega328P based development board with 14 digital I/O pins, 6 analog inputs and USB programming. Primary board for first and second semester projects.",
    qty: 42,
    minQty: 15,
    unit: "pcs",
    location: "Lab A · Rack 1 · Bin 03",
    supplierId: "SUP-02",
    unitCost: 780,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1002",
    name: "ESP32 DevKit V1",
    categoryId: "CAT-01",
    description:
      "Dual-core Wi-Fi + BLE development board, 30-pin breakout. Used for connected and IoT project workstreams.",
    qty: 28,
    minQty: 12,
    unit: "pcs",
    location: "Lab A · Rack 1 · Bin 05",
    supplierId: "SUP-01",
    unitCost: 620,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1003",
    name: "Raspberry Pi 4 Model B (4GB)",
    categoryId: "CAT-01",
    description:
      "Single-board computer with quad-core Cortex-A72, dual HDMI and Gigabit Ethernet. Reserved for vision and edge-compute projects.",
    qty: 9,
    minQty: 6,
    unit: "pcs",
    location: "Lab A · Secure cabinet · Shelf 2",
    supplierId: "SUP-01",
    unitCost: 5400,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1004",
    name: "STM32 Nucleo-F411RE",
    categoryId: "CAT-01",
    description:
      "ARM Cortex-M4 development board with Arduino-compatible headers and on-board ST-LINK debugger.",
    qty: 4,
    minQty: 5,
    unit: "pcs",
    location: "Lab A · Rack 1 · Bin 09",
    supplierId: "SUP-04",
    unitCost: 1650,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1005",
    name: "BBC micro:bit v2",
    categoryId: "CAT-01",
    description:
      "Pocket-sized microcontroller with LED matrix, radio and motion sensing. Used in the first-year outreach workshop.",
    qty: 0,
    minQty: 10,
    unit: "pcs",
    location: "Lab B · Rack 2 · Bin 01",
    supplierId: "SUP-03",
    unitCost: 1450,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1010",
    name: "HC-SR04 Ultrasonic Sensor",
    categoryId: "CAT-02",
    description: "2–400 cm non-contact distance sensor with 40 kHz transmitter and receiver pair.",
    qty: 56,
    minQty: 20,
    unit: "pcs",
    location: "Lab A · Rack 2 · Bin 11",
    supplierId: "SUP-01",
    unitCost: 120,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1011",
    name: "DHT11 Temperature & Humidity Sensor",
    categoryId: "CAT-02",
    description: "Low-cost digital temperature (0–50 °C) and relative humidity (20–90%) sensor.",
    qty: 18,
    minQty: 20,
    unit: "pcs",
    location: "Lab A · Rack 2 · Bin 12",
    supplierId: "SUP-03",
    unitCost: 95,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1012",
    name: "MPU6050 IMU Module",
    categoryId: "CAT-02",
    description:
      "Six-axis accelerometer and gyroscope with I²C interface. Core sensor for the sign-language glove.",
    qty: 34,
    minQty: 10,
    unit: "pcs",
    location: "Lab A · Rack 2 · Bin 14",
    supplierId: "SUP-01",
    unitCost: 210,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1013",
    name: "Capacitive Soil Moisture Sensor",
    categoryId: "CAT-02",
    description: "Corrosion-resistant analog soil moisture probe, 3.3–5 V supply.",
    qty: 12,
    minQty: 8,
    unit: "pcs",
    location: "Lab B · Rack 1 · Bin 04",
    supplierId: "SUP-01",
    unitCost: 140,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1014",
    name: "MQ-135 Air Quality Sensor",
    categoryId: "CAT-02",
    description: "Wide-range gas sensor for ammonia, NOx, benzene and smoke detection.",
    qty: 6,
    minQty: 6,
    unit: "pcs",
    location: "Lab B · Rack 1 · Bin 06",
    supplierId: "SUP-03",
    unitCost: 340,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1015",
    name: "VL53L0X Time-of-Flight Sensor",
    categoryId: "CAT-02",
    description: "Laser distance sensor up to 2 m with millimetre resolution and I²C output.",
    qty: 21,
    minQty: 8,
    unit: "pcs",
    location: "Lab A · Rack 2 · Bin 16",
    supplierId: "SUP-01",
    unitCost: 460,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1016",
    name: "Raspberry Pi Camera Module 5MP",
    categoryId: "CAT-02",
    description: "CSI camera module for Raspberry Pi boards, 5 MP with fixed focus lens.",
    qty: 0,
    minQty: 5,
    unit: "pcs",
    location: "Lab A · Secure cabinet · Shelf 3",
    supplierId: "SUP-01",
    unitCost: 850,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1017",
    name: "Flex Sensor 2.2 inch",
    categoryId: "CAT-02",
    description: "Bend-sensitive resistive sensor for glove-based gesture capture. Newly stocked for Team Halo.",
    qty: 12,
    minQty: 6,
    unit: "pcs",
    location: "Lab A · Rack 2 · Bin 18",
    supplierId: "SUP-01",
    unitCost: 380,
    createdDaysAgo: 4,
  },
  {
    id: "ITM-1018",
    name: "LoRa SX1278 Module 433 MHz",
    categoryId: "CAT-02",
    description: "Long-range, low-power radio transceiver module for the disaster response mesh trial.",
    qty: 14,
    minQty: 6,
    unit: "pcs",
    location: "Lab B · Rack 3 · Bin 02",
    supplierId: "SUP-02",
    unitCost: 540,
    createdDaysAgo: 11,
  },
  {
    id: "ITM-1020",
    name: "16×2 Character LCD (I²C)",
    categoryId: "CAT-03",
    description: "Blue backlit character display with I²C backpack pre-soldered.",
    qty: 26,
    minQty: 10,
    unit: "pcs",
    location: "Lab A · Rack 3 · Bin 02",
    supplierId: "SUP-02",
    unitCost: 210,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1021",
    name: "L298N Motor Driver Module",
    categoryId: "CAT-03",
    description: "Dual H-bridge driver, 2 A per channel, 5–35 V motor supply.",
    qty: 15,
    minQty: 8,
    unit: "pcs",
    location: "Lab A · Rack 3 · Bin 03",
    supplierId: "SUP-02",
    unitCost: 180,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1022",
    name: "SG90 Micro Servo",
    categoryId: "CAT-03",
    description: "9 g hobby servo with 180° travel and 1.8 kg·cm stall torque.",
    qty: 64,
    minQty: 25,
    unit: "pcs",
    location: "Lab A · Rack 3 · Bin 04",
    supplierId: "SUP-02",
    unitCost: 145,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1023",
    name: "Resistor Assortment Kit",
    categoryId: "CAT-03",
    description: "600-piece 1/4 W metal film kit, 30 common values from 10 Î© to 1 MÎ©.",
    qty: 23,
    minQty: 8,
    unit: "kits",
    location: "Lab A · Rack 3 · Bin 06",
    supplierId: "SUP-03",
    unitCost: 260,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1024",
    name: "Capacitor Assortment Kit",
    categoryId: "CAT-03",
    description: "240-piece electrolytic and ceramic capacitor kit, 10 V–50 V ratings.",
    qty: 17,
    minQty: 6,
    unit: "kits",
    location: "Lab A · Rack 3 · Bin 07",
    supplierId: "SUP-03",
    unitCost: 310,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1025",
    name: "5V 2-Channel Relay Module",
    categoryId: "CAT-03",
    description: "Opto-isolated relay board rated 10 A at 250 V AC per channel.",
    qty: 11,
    minQty: 6,
    unit: "pcs",
    location: "Lab A · Rack 3 · Bin 08",
    supplierId: "SUP-01",
    unitCost: 150,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1026",
    name: "Half-size Breadboard (400 pt)",
    categoryId: "CAT-03",
    description: "Solderless breadboard with 400 tie points and adhesive backing.",
    qty: 48,
    minQty: 15,
    unit: "pcs",
    location: "Lab A · Rack 3 · Bin 10",
    supplierId: "SUP-01",
    unitCost: 85,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1027",
    name: "Jumper Wire Set (M-M, 40 pcs)",
    categoryId: "CAT-03",
    description: "Ribbon of 20 cm male-to-male jumper leads, colour coded.",
    qty: 38,
    minQty: 15,
    unit: "sets",
    location: "Lab A · Rack 3 · Bin 11",
    supplierId: "SUP-01",
    unitCost: 120,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1030",
    name: "18650 Li-ion Cell 2600 mAh",
    categoryId: "CAT-04",
    description: "Rechargeable 3.7 V cylindrical cell, tested and capacity-tagged on receipt.",
    qty: 54,
    minQty: 25,
    unit: "pcs",
    location: "Lab B · Battery locker · Tray 1",
    supplierId: "SUP-01",
    unitCost: 210,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1031",
    name: "TP4056 Charging Module",
    categoryId: "CAT-04",
    description: "Single-cell Li-ion charger with protection circuit, USB-C input.",
    qty: 31,
    minQty: 12,
    unit: "pcs",
    location: "Lab B · Rack 1 · Bin 08",
    supplierId: "SUP-01",
    unitCost: 75,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1032",
    name: "5V 2A DC Adapter",
    categoryId: "CAT-04",
    description: "Regulated wall adapter with 5.5 × 2.1 mm barrel jack. Bench and project use.",
    qty: 19,
    minQty: 10,
    unit: "pcs",
    location: "Lab B · Rack 1 · Bin 09",
    supplierId: "SUP-06",
    unitCost: 320,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1033",
    name: "5V 10W Solar Panel",
    categoryId: "CAT-04",
    description: "Monocrystalline panel, 5 V / 2 A peak with sealed junction box.",
    qty: 6,
    minQty: 5,
    unit: "pcs",
    location: "Store room · Shelf 4",
    supplierId: "SUP-01",
    unitCost: 780,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1034",
    name: "12V 7Ah SLA Battery",
    categoryId: "CAT-04",
    description: "Sealed lead-acid battery for rover and field-deployment power.",
    qty: 3,
    minQty: 4,
    unit: "pcs",
    location: "Store room · Battery bay",
    supplierId: "SUP-06",
    unitCost: 1250,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1040",
    name: "N20 Gear Motor 300 rpm",
    categoryId: "CAT-05",
    description: "Brushed DC gear motor, 6 V, 300 rpm output with 3 mm D-shaft.",
    qty: 46,
    minQty: 18,
    unit: "pcs",
    location: "Lab B · Rack 2 · Bin 05",
    supplierId: "SUP-02",
    unitCost: 320,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1041",
    name: "SG90 Servo Bracket Set",
    categoryId: "CAT-05",
    description: "ABS mounting bracket with horn screws for standard 9 g servos.",
    qty: 22,
    minQty: 10,
    unit: "sets",
    location: "Lab B · Rack 2 · Bin 06",
    supplierId: "SUP-02",
    unitCost: 110,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1042",
    name: "Robot Wheel Set (65 mm)",
    categoryId: "CAT-05",
    description: "Rubber-tyred wheel pair with matching hubs for N20 gear motors.",
    qty: 29,
    minQty: 12,
    unit: "sets",
    location: "Lab B · Rack 2 · Bin 07",
    supplierId: "SUP-02",
    unitCost: 240,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1043",
    name: "Ball Bearing Set (608ZZ)",
    categoryId: "CAT-05",
    description: "10-pack shielded deep-groove bearings, 8 × 22 × 7 mm.",
    qty: 8,
    minQty: 10,
    unit: "packs",
    location: "Lab B · Rack 2 · Bin 09",
    supplierId: "SUP-06",
    unitCost: 160,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1044",
    name: "Aluminium Extrusion 20×20 (1 m)",
    categoryId: "CAT-05",
    description: "Anodised T-slot profile for frames and gantries.",
    qty: 14,
    minQty: 6,
    unit: "pcs",
    location: "Store room · Long stock rack",
    supplierId: "SUP-05",
    unitCost: 390,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1045",
    name: "M3 Screw & Nut Kit",
    categoryId: "CAT-05",
    description: "Assorted M3 hex bolts, nuts and washers in a compartmented box.",
    qty: 27,
    minQty: 8,
    unit: "kits",
    location: "Lab B · Rack 2 · Bin 12",
    supplierId: "SUP-06",
    unitCost: 290,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1050",
    name: "Digital Multimeter (UT139C)",
    categoryId: "CAT-06",
    description: "True-RMS bench multimeter with capacitance and temperature measurement.",
    qty: 7,
    minQty: 4,
    unit: "pcs",
    location: "Lab A · Tool crib · Drawer 1",
    supplierId: "SUP-04",
    unitCost: 3200,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1051",
    name: "Soldering Station 60W",
    categoryId: "CAT-06",
    description: "Temperature-controlled soldering station with spare tips and stand.",
    qty: 5,
    minQty: 3,
    unit: "pcs",
    location: "Lab A · Tool crib · Drawer 2",
    supplierId: "SUP-04",
    unitCost: 2450,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1052",
    name: "Digital Vernier Caliper",
    categoryId: "CAT-06",
    description: "150 mm stainless steel caliper with 0.01 mm resolution.",
    qty: 9,
    minQty: 4,
    unit: "pcs",
    location: "Lab A · Tool crib · Drawer 3",
    supplierId: "SUP-04",
    unitCost: 1150,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1053",
    name: "Precision Screwdriver Set",
    categoryId: "CAT-06",
    description: "24-piece interchangeable bit set with ESD-safe handle.",
    qty: 12,
    minQty: 5,
    unit: "sets",
    location: "Lab A · Tool crib · Drawer 4",
    supplierId: "SUP-06",
    unitCost: 680,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1054",
    name: "Hot Air Rework Station",
    categoryId: "CAT-06",
    description: "850 W adjustable hot air station for SMD rework. Bench 3 only.",
    qty: 2,
    minQty: 2,
    unit: "pcs",
    location: "Lab A · Bench 3",
    supplierId: "SUP-04",
    unitCost: 4600,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1060",
    name: "PLA Filament 1.75 mm (1 kg)",
    categoryId: "CAT-07",
    description: "Rigid PLA spool for FDM printing. Store sealed with desiccant.",
    qty: 16,
    minQty: 8,
    unit: "spools",
    location: "Fab corner · Dry cabinet",
    supplierId: "SUP-05",
    unitCost: 1150,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1061",
    name: "MDF Board 3 mm (600×400)",
    categoryId: "CAT-07",
    description: "Laser-safe medium-density fibreboard sheet.",
    qty: 24,
    minQty: 8,
    unit: "sheets",
    location: "Fab corner · Sheet rack A",
    supplierId: "SUP-05",
    unitCost: 180,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1062",
    name: "Clear Acrylic Sheet 3 mm",
    categoryId: "CAT-07",
    description: "Cast acrylic sheet for enclosures and display panels.",
    qty: 11,
    minQty: 6,
    unit: "sheets",
    location: "Fab corner · Sheet rack B",
    supplierId: "SUP-05",
    unitCost: 320,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1063",
    name: "Aluminium Sheet 1 mm",
    categoryId: "CAT-07",
    description: "3003 grade aluminium sheet, 500 × 300 mm, for brackets and panels.",
    qty: 9,
    minQty: 5,
    unit: "sheets",
    location: "Fab corner · Sheet rack C",
    supplierId: "SUP-05",
    unitCost: 280,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1070",
    name: "Nitrile Gloves (Box of 100)",
    categoryId: "CAT-08",
    description: "Powder-free nitrile gloves, size M, for soldering and chemical handling.",
    qty: 13,
    minQty: 6,
    unit: "boxes",
    location: "Lab A · Safety station",
    supplierId: "SUP-03",
    unitCost: 480,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1071",
    name: "Safety Goggles",
    categoryId: "CAT-08",
    description: "Anti-fog polycarbonate goggles, EN 166 rated.",
    qty: 18,
    minQty: 10,
    unit: "pcs",
    location: "Lab A · Safety station",
    supplierId: "SUP-06",
    unitCost: 220,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1072",
    name: "Heat-resistant Silicone Mat",
    categoryId: "CAT-08",
    description: "500 × 350 mm soldering mat with screw tray compartments.",
    qty: 7,
    minQty: 4,
    unit: "pcs",
    location: "Lab A · Bench 2",
    supplierId: "SUP-06",
    unitCost: 350,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1073",
    name: "First Aid Refill Kit",
    categoryId: "CAT-08",
    description: "Burn dressings, antiseptic wipes, gauze and gloves for lab first-aid boxes.",
    qty: 5,
    minQty: 3,
    unit: "kits",
    location: "Lab A · Safety station",
    supplierId: "SUP-06",
    unitCost: 640,
    createdDaysAgo: 330,
  },
  {
    id: "ITM-1074",
    name: "Anti-static Wrist Strap",
    categoryId: "CAT-08",
    description: "Adjustable ESD wrist strap with coiled cord and crocodile clip.",
    qty: 16,
    minQty: 8,
    unit: "pcs",
    location: "Lab A · Safety station",
    supplierId: "SUP-03",
    unitCost: 240,
    createdDaysAgo: 18,
  },
];

/* ------------------------------------------------------------------ */
/* Projects                                                            */
/* ------------------------------------------------------------------ */

type AllocSeed = {
  itemId: string;
  issued: number;
  consumed: number;
  returned: number;
  outDaysAgo: number;
  returnDaysAgo?: number;
  requestId?: string;
};

type ProjectSeed = {
  id: string;
  name: string;
  description: string;
  team: string[];
  supervisor: string;
  startDate: string;
  endDate: string;
  status: Project["status"];
  alloc: AllocSeed[];
  required: { name: string; qty: number; unit: string; itemId?: string }[];
};

const projectSeeds: ProjectSeed[] = [
  {
    id: "PBL-2026-014",
    name: "Smart Campus Energy Monitor",
    description:
      "A LoRa-connected energy metering node that streams block-level consumption to the campus dashboard and flags anomalous load patterns after hours.",
    team: ["Aarav Sharma", "Diya Patel", "Kabir Menon", "Ishita Rao"],
    supervisor: "Dr. Ananya Rao",
    startDate: daysAgo(226, 9),
    endDate: inDays(14),
    status: "active",
    alloc: [
      { itemId: "ITM-1002", issued: 6, consumed: 2, returned: 1, outDaysAgo: 60, returnDaysAgo: 20 },
      { itemId: "ITM-1033", issued: 2, consumed: 1, returned: 0, outDaysAgo: 60 },
      { itemId: "ITM-1030", issued: 8, consumed: 6, returned: 2, outDaysAgo: 59, returnDaysAgo: 12 },
      { itemId: "ITM-1032", issued: 2, consumed: 1, returned: 0, outDaysAgo: 58 },
      { itemId: "ITM-1020", issued: 2, consumed: 1, returned: 0, outDaysAgo: 30 },
    ],
    required: [
      { name: "Custom metering PCB", qty: 3, unit: "boards" },
      { name: "IP54 enclosure", qty: 3, unit: "pcs" },
      { name: "CT clamp 30 A", qty: 6, unit: "pcs" },
    ],
  },
  {
    id: "PBL-2026-009",
    name: "Autonomous Greenhouse Rover",
    description:
      "A four-wheel differential rover that patrols a polyhouse, samples soil moisture and drives a drip-line valve without human intervention.",
    team: ["Rohan Gupta", "Ananya Singh", "Vivaan Reddy", "Zara Khan"],
    supervisor: "Prof. K. Menon",
    startDate: daysAgo(277, 9),
    endDate: inDays(28),
    status: "active",
    alloc: [
      { itemId: "ITM-1040", issued: 8, consumed: 4, returned: 2, outDaysAgo: 90, returnDaysAgo: 25 },
      { itemId: "ITM-1042", issued: 4, consumed: 2, returned: 0, outDaysAgo: 90 },
      { itemId: "ITM-1021", issued: 3, consumed: 2, returned: 0, outDaysAgo: 88 },
      { itemId: "ITM-1010", issued: 4, consumed: 3, returned: 0, outDaysAgo: 85 },
      { itemId: "ITM-1001", issued: 6, consumed: 3, returned: 1, outDaysAgo: 84, returnDaysAgo: 18 },
      { itemId: "ITM-1013", issued: 4, consumed: 2, returned: 1, outDaysAgo: 60, returnDaysAgo: 9 },
      { itemId: "ITM-1034", issued: 2, consumed: 1, returned: 0, outDaysAgo: 45 },
      { itemId: "ITM-1061", issued: 6, consumed: 4, returned: 1, outDaysAgo: 44, returnDaysAgo: 14 },
    ],
    required: [
      { name: "Drip valve solenoid", qty: 2, unit: "pcs" },
      { name: "Custom rover chassis", qty: 1, unit: "unit" },
      { name: "Weatherproof camera mount", qty: 2, unit: "pcs" },
    ],
  },
  {
    id: "PBL-2026-021",
    name: "Sign Language Translation Glove",
    description:
      "A wearable glove with flex and inertial sensors that recognises 24 ISL hand signs and speaks the translated word through an on-glove speaker.",
    team: ["Neha Kulkarni", "Aditya Bose", "Fatima Sheikh"],
    supervisor: "Dr. Nikhil Verma",
    startDate: daysAgo(152, 9),
    endDate: inDays(16),
    status: "active",
    alloc: [
      { itemId: "ITM-1012", issued: 6, consumed: 4, returned: 1, outDaysAgo: 55, returnDaysAgo: 10 },
      { itemId: "ITM-1002", issued: 4, consumed: 2, returned: 0, outDaysAgo: 55 },
      { itemId: "ITM-1022", issued: 5, consumed: 3, returned: 0, outDaysAgo: 57, requestId: "REQ-2032" },
      { itemId: "ITM-1027", issued: 6, consumed: 3, returned: 1, outDaysAgo: 54, returnDaysAgo: 8 },
      { itemId: "ITM-1026", issued: 4, consumed: 2, returned: 0, outDaysAgo: 54 },
      { itemId: "ITM-1060", issued: 3, consumed: 2, returned: 0, outDaysAgo: 40 },
    ],
    required: [
      { name: "Flex sensor (2.2 inch)", qty: 5, unit: "pcs", itemId: "ITM-1017" },
      { name: "Conductive thread spool", qty: 2, unit: "spools" },
      { name: "Vibration speaker module", qty: 1, unit: "pcs" },
    ],
  },
  {
    id: "PBL-2026-003",
    name: "Campus Waste Segregation Bin",
    description:
      "A smart bin that classifies waste into wet, dry and e-waste streams using a capacitive sensor array and a servo-driven flap mechanism.",
    team: ["Siddharth Jain", "Meghna Pillai", "Arnav Kapoor"],
    supervisor: "Prof. Sneha Iyer",
    startDate: daysAgo(310, 9),
    endDate: daysAgo(208, 17),
    status: "completed",
    alloc: [
      { itemId: "ITM-1001", issued: 4, consumed: 4, returned: 0, outDaysAgo: 300 },
      { itemId: "ITM-1022", issued: 6, consumed: 6, returned: 0, outDaysAgo: 298, requestId: "REQ-2031" },
      { itemId: "ITM-1010", issued: 3, consumed: 3, returned: 0, outDaysAgo: 297 },
      { itemId: "ITM-1061", issued: 8, consumed: 8, returned: 0, outDaysAgo: 296 },
      { itemId: "ITM-1062", issued: 4, consumed: 3, returned: 1, outDaysAgo: 295, returnDaysAgo: 250 },
      { itemId: "ITM-1025", issued: 2, consumed: 2, returned: 0, outDaysAgo: 280 },
    ],
    required: [
      { name: "Classification sensor array", qty: 1, unit: "unit" },
      { name: "Servo flap linkage", qty: 2, unit: "sets" },
      { name: "Bin shell fabrication", qty: 1, unit: "unit" },
    ],
  },
  {
    id: "PBL-2026-027",
    name: "Disaster Response LoRa Mesh",
    description:
      "A self-healing mesh of battery-backed LoRa nodes that relays distress messages and sensor readings from flood-affected zones to a field base station.",
    team: ["Tara Iyer", "Yash Deshmukh", "Aarohi Naik"],
    supervisor: "Dr. Arjun Nair",
    startDate: daysAgo(105, 9),
    endDate: inDays(98),
    status: "on-hold",
    alloc: [
      { itemId: "ITM-1002", issued: 8, consumed: 1, returned: 0, outDaysAgo: 80 },
      { itemId: "ITM-1033", issued: 2, consumed: 0, returned: 0, outDaysAgo: 75 },
      { itemId: "ITM-1030", issued: 6, consumed: 1, returned: 0, outDaysAgo: 74 },
      { itemId: "ITM-1032", issued: 2, consumed: 1, returned: 0, outDaysAgo: 70 },
    ],
    required: [
      { name: "LoRa SX1278 module", qty: 8, unit: "pcs", itemId: "ITM-1018" },
      { name: "Weatherproof node enclosure", qty: 8, unit: "pcs" },
      { name: "Solar charge controller", qty: 4, unit: "pcs" },
    ],
  },
  {
    id: "PBL-2026-031",
    name: "Low-Cost Water Quality Tester",
    description:
      "A portable turbidity and pH tester for campus water bodies, with a companion app that logs readings and maps contamination hot spots.",
    team: ["Dev Malhotra", "Saanvi Bhat", "Omar Farooq"],
    supervisor: "Prof. Meera Joshi",
    startDate: daysAgo(9, 9),
    endDate: inDays(121),
    status: "planning",
    alloc: [],
    required: [
      { name: "Turbidity sensor module", qty: 2, unit: "pcs" },
      { name: "pH probe kit", qty: 2, unit: "kits" },
      { name: "Waterproof enclosure", qty: 2, unit: "pcs" },
      { name: "DHT11 sensor", qty: 4, unit: "pcs", itemId: "ITM-1011" },
    ],
  },
];

/* ------------------------------------------------------------------ */
/* Transaction drafts                                                  */
/* ------------------------------------------------------------------ */

type Draft = {
  type: TransactionType;
  itemId: string;
  qty: number;
  delta: number;
  at: string;
  actor: string;
  note: string;
  projectId?: string;
  requestId?: string;
  supplierId?: string;
};

const ADMIN = "Himaneesh Reddy";
const TECH = "Lakshmi Prasad";

const drafts: Draft[] = [];

/* Restocks and receipts */
const restocks: Array<[string, number, number, string, string]> = [
  ["ITM-1001", 20, 22, "SUP-01", "PO-2291 · weekly electronics replenishment"],
  ["ITM-1002", 15, 18, "SUP-01", "PO-2291 · ESP32 restock"],
  ["ITM-1010", 30, 12, "SUP-01", "PO-2294 · ultrasonic sensors"],
  ["ITM-1027", 20, 30, "SUP-01", "PO-2288 · jumper wire sets"],
  ["ITM-1022", 40, 25, "SUP-02", "PO-2283 · servo bulk pack"],
  ["ITM-1040", 30, 40, "SUP-02", "PO-2275 · gear motors"],
  ["ITM-1042", 15, 45, "SUP-02", "PO-2275 · wheel sets"],
  ["ITM-1011", 25, 35, "SUP-03", "PO-2280 · DHT11 sensors"],
  ["ITM-1014", 10, 20, "SUP-03", "PO-2281 · air quality sensors"],
  ["ITM-1004", 5, 50, "SUP-04", "PO-2272 · STM32 boards"],
  ["ITM-1050", 3, 65, "SUP-04", "PO-2268 · multimeters"],
  ["ITM-1060", 10, 15, "SUP-05", "PO-2296 · PLA filament"],
  ["ITM-1062", 8, 28, "SUP-05", "PO-2286 · acrylic sheets"],
  ["ITM-1061", 20, 55, "SUP-05", "PO-2270 · MDF sheets"],
  ["ITM-1070", 12, 9, "SUP-03", "PO-2299 · nitrile gloves"],
  ["ITM-1071", 15, 33, "SUP-06", "Indent 148 · safety goggles"],
  ["ITM-1045", 20, 60, "SUP-06", "Indent 131 · fastener kits"],
  ["ITM-1020", 12, 38, "SUP-02", "PO-2284 · I²C displays"],
  ["ITM-1033", 4, 35, "SUP-01", "PO-2282 · solar panels"],
  ["ITM-1023", 10, 70, "SUP-03", "PO-2266 · resistor kits"],
  ["ITM-1026", 20, 65, "SUP-01", "PO-2269 · breadboards"],
  ["ITM-1032", 10, 42, "SUP-06", "Indent 137 · DC adapters"],
  ["ITM-1030", 20, 48, "SUP-01", "PO-2278 · 18650 cells, capacity tested"],
];

restocks.forEach(([itemId, qty, days, supplierId, note], i) => {
  drafts.push({
    type: "in",
    itemId,
    qty,
    delta: qty,
    at: daysAgo(days, 9 + (i % 7), (i * 13) % 60),
    actor: i % 4 === 0 ? TECH : ADMIN,
    note,
    supplierId,
  });
});

/* Stock adjustments: damages, cycle counts, write-offs */
const adjustments: Array<[string, number, number, string]> = [
  ["ITM-1030", -2, 7, "Two cells failed capacity test during pre-issue check"],
  ["ITM-1022", 3, 5, "Cycle count correction · rack 3 bin 4"],
  ["ITM-1062", -1, 16, "Sheet cracked during laser cutting"],
  ["ITM-1027", -2, 11, "Leads damaged during sorting"],
  ["ITM-1061", -1, 23, "Warped sheet discarded"],
  ["ITM-1011", -1, 6, "Damaged in transit; vendor credit pending"],
  ["ITM-1070", -2, 3, "Consumed during PCB cleaning workshop"],
  ["ITM-1014", -1, 19, "Sensor drift; removed from service"],
  ["ITM-1025", 1, 21, "Found during rack audit · bin 08"],
  ["ITM-1042", -1, 40, "Hub cracked on test rig"],
  ["ITM-1005", -12, 26, "Issued to first-year outreach workshop, awaiting return"],
  ["ITM-1016", -3, 15, "All units deployed to capstone demo kits"],
];

adjustments.forEach(([itemId, delta, days, note], i) => {
  drafts.push({
    type: "adjust",
    itemId,
    qty: Math.abs(delta),
    delta,
    at: daysAgo(days, 11 + (i % 6), (i * 17) % 60),
    actor: i % 3 === 0 ? ADMIN : TECH,
    note,
  });
});

/* Project issues and returns */
projectSeeds.forEach((project) => {
  project.alloc.forEach((a, idx) => {
    drafts.push({
      type: "out",
      itemId: a.itemId,
      qty: a.issued,
      delta: -a.issued,
      at: daysAgo(a.outDaysAgo, 10 + (idx % 5), (idx * 11) % 60),
      actor: ADMIN,
      note: `Issued to ${project.id} · ${project.name}`,
      projectId: project.id,
      requestId: a.requestId,
    });
    if (a.returned > 0) {
      drafts.push({
        type: "return",
        itemId: a.itemId,
        qty: a.returned,
        delta: a.returned,
        at: daysAgo(a.returnDaysAgo ?? Math.max(1, a.outDaysAgo - 10), 15, (idx * 19) % 60),
        actor: TECH,
        note: `Returned from ${project.id} · ${project.name}`,
        projectId: project.id,
      });
    }
  });
});

/* Compute opening balances backwards from the target quantity so that the
   ledger and the on-hand quantity can never disagree. */
const openingByItem = new Map<string, number>();
const netByItem = new Map<string, number>();
drafts.forEach((d) => {
  netByItem.set(d.itemId, (netByItem.get(d.itemId) ?? 0) + d.delta);
});

itemSeeds.forEach((item) => {
  const net = netByItem.get(item.id) ?? 0;
  const opening = item.qty - net;
  openingByItem.set(item.id, Math.max(0, opening));
  if (opening > 0) {
    drafts.push({
      type: "in",
      itemId: item.id,
      qty: opening,
      delta: opening,
      at: daysAgo(item.createdDaysAgo, 8, 0),
      actor: ADMIN,
      note: "Opening stock · semester baseline count",
      supplierId: item.supplierId,
    });
  }
});

/* Assign ids by chronological order, then walk balances per item */
const sorted = [...drafts].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());

const balances = new Map<string, number>();
const transactions: Transaction[] = sorted.map((d, i) => {
  const current = balances.get(d.itemId) ?? 0;
  const next = Math.max(0, current + d.delta);
  balances.set(d.itemId, next);
  return {
    id: `TXN-${String(1001 + i).padStart(4, "0")}`,
    type: d.type,
    itemId: d.itemId,
    qty: d.qty,
    delta: d.delta,
    balanceAfter: next,
    projectId: d.projectId,
    requestId: d.requestId,
    supplierId: d.supplierId,
    actor: d.actor,
    note: d.note,
    at: d.at,
  };
});

/* ------------------------------------------------------------------ */
/* Materialise items                                                   */
/* ------------------------------------------------------------------ */

const latestByItem = new Map<string, string>();
transactions.forEach((t) => {
  latestByItem.set(t.itemId, t.at);
});

const items: Item[] = itemSeeds.map((seed) => {
  const last = latestByItem.get(seed.id);
  return {
    id: seed.id,
    name: seed.name,
    categoryId: seed.categoryId,
    description: seed.description,
    qty: balances.get(seed.id) ?? 0,
    minQty: seed.minQty,
    unit: seed.unit,
    location: seed.location,
    supplierId: seed.supplierId,
    unitCost: seed.unitCost,
    createdAt: daysAgo(seed.createdDaysAgo, 8),
    updatedAt: last ?? daysAgo(seed.createdDaysAgo, 8),
  };
});

/* ------------------------------------------------------------------ */
/* Projects                                                            */
/* ------------------------------------------------------------------ */

const projects: Project[] = projectSeeds.map((p) => {
  const allocations: Allocation[] = p.alloc.map((a) => ({
    itemId: a.itemId,
    issued: a.issued,
    consumed: a.consumed,
    returned: a.returned,
  }));
  return {
    id: p.id,
    name: p.name,
    description: p.description,
    team: p.team,
    supervisor: p.supervisor,
    startDate: p.startDate,
    endDate: p.endDate,
    status: p.status,
    allocations,
    required: p.required,
  };
});

/* ------------------------------------------------------------------ */
/* Requests                                                            */
/* ------------------------------------------------------------------ */

type RequestSeed = {
  id: string;
  projectId: string;
  requestedBy: string;
  lines: Array<[string, number]>;
  status: RequestStatus;
  priority: Priority;
  note: string;
  createdDaysAgo: number;
  reviewedDaysAgo?: number;
  reviewedBy?: string;
  rejectReason?: string;
  issuedDaysAgo?: number;
};

const requestSeeds: RequestSeed[] = [
  {
    id: "REQ-2041",
    projectId: "PBL-2026-027",
    requestedBy: "Tara Iyer",
    lines: [
      ["ITM-1018", 4],
      ["ITM-1033", 2],
      ["ITM-1030", 4],
    ],
    status: "pending",
    priority: "urgent",
    note: "Mesh node field trial is scheduled for 22 Nov. Need radio modules and panel power to assemble the first three nodes.",
    createdDaysAgo: 0,
  },
  {
    id: "REQ-2040",
    projectId: "PBL-2026-031",
    requestedBy: "Dev Malhotra",
    lines: [
      ["ITM-1011", 24],
      ["ITM-1014", 2],
      ["ITM-1020", 2],
      ["ITM-1026", 2],
    ],
    status: "pending",
    priority: "high",
    note: "Environmental sensing rig for the water test bench. DHT11 count includes spares for the field trial.",
    createdDaysAgo: 1,
  },
  {
    id: "REQ-2039",
    projectId: "PBL-2026-009",
    requestedBy: "Rohan Gupta",
    lines: [
      ["ITM-1040", 4],
      ["ITM-1042", 2],
      ["ITM-1021", 2],
      ["ITM-1045", 2],
    ],
    status: "pending",
    priority: "normal",
    note: "Second rover prototype. The previous drive train is with the first-year demo team.",
    createdDaysAgo: 2,
  },
  {
    id: "REQ-2038",
    projectId: "PBL-2026-021",
    requestedBy: "Neha Kulkarni",
    lines: [
      ["ITM-1015", 4],
      ["ITM-1002", 2],
      ["ITM-1060", 2],
    ],
    status: "pending",
    priority: "high",
    note: "Adding a distance channel to the glove rig and printing a new wrist housing for the review on 21 Nov.",
    createdDaysAgo: 3,
  },
  {
    id: "REQ-2037",
    projectId: "PBL-2026-014",
    requestedBy: "Aarav Sharma",
    lines: [
      ["ITM-1050", 1],
      ["ITM-1051", 1],
    ],
    status: "pending",
    priority: "low",
    note: "Bench day on Friday to reflow the metering board. Requesting one meter and one station for the 2 pm slot.",
    createdDaysAgo: 4,
  },
  {
    id: "REQ-2036",
    projectId: "PBL-2026-009",
    requestedBy: "Ananya Singh",
    lines: [
      ["ITM-1034", 1],
      ["ITM-1025", 2],
    ],
    status: "approved",
    priority: "high",
    note: "Field power backup for the rover's final demo.",
    createdDaysAgo: 5,
    reviewedDaysAgo: 4,
    reviewedBy: "Himaneesh Reddy",
  },
  {
    id: "REQ-2035",
    projectId: "PBL-2026-014",
    requestedBy: "Ishita Rao",
    lines: [
      ["ITM-1032", 1],
      ["ITM-1027", 2],
    ],
    status: "approved",
    priority: "normal",
    note: "Test bench wiring for the sensor calibration run.",
    createdDaysAgo: 6,
    reviewedDaysAgo: 5,
    reviewedBy: "Lakshmi Prasad",
  },
  {
    id: "REQ-2034",
    projectId: "PBL-2026-031",
    requestedBy: "Saanvi Bhat",
    lines: [
      ["ITM-1003", 6],
      ["ITM-1016", 2],
    ],
    status: "rejected",
    priority: "urgent",
    note: "Vision rig for reading the pH colour strip.",
    createdDaysAgo: 8,
    reviewedDaysAgo: 7,
    reviewedBy: "Himaneesh Reddy",
    rejectReason:
      "Raspberry Pi units are reserved for the capstone demo until 20 Nov and camera modules are fully committed. Re-submit for a single Pi unit in week 12.",
  },
  {
    id: "REQ-2033",
    projectId: "PBL-2026-027",
    requestedBy: "Yash Deshmukh",
    lines: [["ITM-1054", 1]],
    status: "rejected",
    priority: "normal",
    note: "Hot air station for replacing the radio module headers.",
    createdDaysAgo: 12,
    reviewedDaysAgo: 11,
    reviewedBy: "Himaneesh Reddy",
    rejectReason:
      "Bench equipment cannot leave Lab A. Book a rework slot and the technician will set up the station for you.",
  },
  {
    id: "REQ-2032",
    projectId: "PBL-2026-021",
    requestedBy: "Neha Kulkarni",
    lines: [["ITM-1022", 5]],
    status: "issued",
    priority: "normal",
    note: "Servos for the finger actuation prototype.",
    createdDaysAgo: 59,
    reviewedDaysAgo: 58,
    reviewedBy: "Himaneesh Reddy",
    issuedDaysAgo: 57,
  },
  {
    id: "REQ-2031",
    projectId: "PBL-2026-003",
    requestedBy: "Siddharth Jain",
    lines: [["ITM-1022", 6]],
    status: "issued",
    priority: "normal",
    note: "Servos for the bin flap mechanism.",
    createdDaysAgo: 301,
    reviewedDaysAgo: 300,
    reviewedBy: "Himaneesh Reddy",
    issuedDaysAgo: 298,
  },
];

const requests: MaterialRequest[] = requestSeeds.map((r) => ({
  id: r.id,
  projectId: r.projectId,
  requestedBy: r.requestedBy,
  lines: r.lines.map(([itemId, qty]) => ({ itemId, qty })),
  status: r.status,
  priority: r.priority,
  note: r.note,
  createdAt: daysAgo(r.createdDaysAgo, 10 + (r.createdDaysAgo % 5), 25),
  reviewedAt: r.reviewedDaysAgo !== undefined ? daysAgo(r.reviewedDaysAgo, 14, 10) : undefined,
  reviewedBy: r.reviewedBy,
  rejectReason: r.rejectReason,
  issuedAt: r.issuedDaysAgo !== undefined ? daysAgo(r.issuedDaysAgo, 11, 40) : undefined,
}));

/* ------------------------------------------------------------------ */
/* Assemble state                                                      */
/* ------------------------------------------------------------------ */

export const seedState: AppState = {
  items,
  categories: seedCategories,
  suppliers: seedSuppliers,
  projects,
  transactions,
  requests,
  settings: {
    orgName: "Meridian Institute of Technology",
    campus: "PBL Innovation Lab · Block C",
    currency: "INR",
    defaultMinThreshold: 10,
    lowStockAlerts: true,
    requestAlerts: true,
    weeklyDigest: true,
    requireApproval: true,
    allowStudentRequests: true,
    semester: "Semester 3 · 2026–27",
  },
  role: "admin",
};

export const seedActor = {
  name: "Himaneesh Reddy",
  role: "admin" as const,
  email: "himaneesh@meridian.edu.in",
};

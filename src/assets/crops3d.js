import * as T from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// Label, plant shape, foliage, harvest color, and harvest shape.
const crops = [
  ["Maíz", "stalk", 0x578639, 0xf2b735, "ear"],
  ["Frijol", "vine", 0x5c9a48, 0x8dc44b, "pod"],
  ["Papa", "root", 0x4b783a, 0xc69556, "tuber"],
  ["Alfalfa", "herb", 0x719547, 0xa27bbc, "flower"],
  ["Plátano", "palm", 0x63843b, 0xe8bc3c, "banana"],
  ["Cebada", "grain", 0x989652, 0xd6ad62, "barley"],
  ["Zanahoria", "root", 0x6e9a39, 0xf58b36, "carrot"],
  ["Garbanzo", "herb", 0x74934e, 0xdbbc76, "chickpea"],
  ["Cítricos", "tree", 0x457e38, 0xf19a23, "round"],
  ["Cacao", "tree", 0x697b3e, 0xa8492b, "cacao"],
  ["Café", "bush", 0x397742, 0xc43037, "berry"],
  ["Algodón", "bush", 0x6e954e, 0xfaf4df, "cotton"],
  ["Frijol caupí", "vine", 0x699d40, 0xa1bd55, "longpod"],
  ["Maní", "root", 0x579247, 0xc89e62, "peanut"],
  ["Olivo", "tree", 0x80936b, 0x423846, "olive"],
  ["Cebolla", "root", 0x6d9e51, 0xc9864b, "onion"],
  ["Soya", "bush", 0x67914c, 0xb0b850, "soy"],
  ["Camote", "root", 0x467a4a, 0xbc6255, "sweet"],
  ["Tomate", "vine", 0x54823c, 0xe54832, "round"],
  ["Trigo", "grain", 0x918746, 0xe6bd6d, "wheat"],
];
const systems = [
  ["Solo cultivo", "none"],
  ["Riego por goteo", "drip"],
  ["Riego por gravedad", "gravity"],
  ["Secano", "rainfed"],
];
const waterEnglish = ["Crop only", "Drip irrigation", "Gravity irrigation", "Rainfed"];
const partEnglish = {
  "Modelo completo": "Whole model", "Tallos": "Stems", "Tronco y ramas": "Trunk and branches",
  "Pseudotallo": "Pseudostem", "Hojas": "Leaves", "Mazorca": "Ear", "Vainas": "Pods",
  "Tubérculos": "Tubers", "Flores": "Flowers", "Racimo": "Bunch", "Espiga con aristas": "Awned head",
  "Raíz de reserva": "Storage root", "Vainas de garbanzo": "Chickpea pods", "Frutos cítricos": "Citrus fruit",
  "Mazorca de cacao": "Cacao pod", "Cerezas de café": "Coffee cherries", "Cápsulas abiertas": "Open bolls",
  "Vainas largas": "Long pods", "Vainas subterráneas": "Underground pods", "Aceitunas": "Olives",
  "Bulbo": "Bulb", "Vainas de soya": "Soybean pods", "Raíces de reserva": "Storage roots",
  "Tomates": "Tomatoes", "Espiga": "Grain head", "Lluvia": "Rain", "Agua": "Water",
  "Tuberías y goteros": "Pipes and emitters", "Surcos": "Furrows",
};
const cropCodes = [
  "mze", "phb", "wpo", "alf", "ban", "brl", "car", "chk", "cit", "coc",
  "cof", "cot", "cow", "grd", "olv", "oni", "soy", "spo", "tom", "whe",
];
const harvestLabels = {
  ear:"Mazorca", pod:"Vainas", tuber:"Tubérculos", flower:"Flores", banana:"Racimo",
  barley:"Espiga con aristas", carrot:"Raíz de reserva", chickpea:"Vainas de garbanzo",
  cacao:"Mazorca de cacao", berry:"Cerezas de café", cotton:"Cápsulas abiertas",
  longpod:"Vainas largas", peanut:"Vainas subterráneas", olive:"Aceitunas",
  onion:"Bulbo", soy:"Vainas de soya", sweet:"Raíces de reserva", wheat:"Espiga",
};

const sphere = new T.SphereGeometry(1, 12, 8);
const cylinder = new T.CylinderGeometry(1, 1, 1, 8);
const cone = new T.ConeGeometry(1, 1, 10);
const box = new T.BoxGeometry(1, 1, 1);
const materials = new Map();

function shape(group, geometry, color, x, y, z, sx, sy, sz) {
  if (!materials.has(color)) materials.set(color, new T.MeshStandardMaterial({ color }));
  const mesh = new T.Mesh(geometry, materials.get(color));
  mesh.position.set(x, y, z);
  mesh.scale.set(sx, sy, sz);
  group.add(mesh);
  return mesh;
}

function stem(group, from, to, color, radius) {
  const start = new T.Vector3(...from);
  const end = new T.Vector3(...to);
  const direction = end.clone().sub(start);
  const middle = start.lerp(end, 0.5);
  const mesh = shape(group, cylinder, color, ...middle.toArray(), radius, direction.length(), radius);
  mesh.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), direction.normalize());
}

function oval(group, color, position, scale, angle = 0) {
  const mesh = shape(group, sphere, color, ...position, ...scale);
  mesh.rotation.z = angle;
  return mesh;
}

function harvest(group, kind, color, x, y, z) {
  const dimensions = {
    ear: [.13,.34,.13], pod: [.08,.27,.07], longpod: [.06,.37,.06], soy: [.12,.16,.08],
    tuber: [.21,.15,.16], sweet: [.29,.13,.13], chickpea: [.12,.12,.10],
    cacao: [.14,.25,.14], berry: [.10,.10,.10], olive: [.10,.15,.10], round: [.15,.15,.15],
  };
  if (kind === "carrot") {
    shape(group, cone, color, x, y, z, .13, .44, .13).rotation.z = Math.PI - .28;
  } else if (["flower", "cotton", "peanut", "banana", "barley", "wheat"].includes(kind)) {
    const count = {flower: 5, cotton: 4, peanut: 3, banana: 4, barley: 8, wheat: 6}[kind];
    for (let i = 0; i < count; i++) {
      if (kind === "barley" || kind === "wheat") {
        const side = i % 2 ? 1 : -1;
        const level = y + i * .045;
        oval(group, color, [x + side * .055, level, z], [.068,.095,.058], -side * .6);
        if (kind === "barley") stem(group, [x,level,z], [x + side * .15,level + .34,z], color, .009);
      } else if (kind === "banana") {
        oval(group, color, [x + i * .065, y - i * .045, z], [.075,.26,.078], -.55 + i * .24);
      } else if (kind === "peanut") {
        oval(group, color, [x + i * .095, y, z], [.08,.085,.085]);
      } else {
        const angle = i * Math.PI * 2 / count;
        oval(group, color, [x + Math.cos(angle) * .09, y + .04, z + Math.sin(angle) * .09],
          kind === "cotton" ? [.105,.105,.105] : [.073,.085,.073]);
      }
    }
  } else if (kind === "onion") {
    oval(group, color, [x,y,z], [.19,.17,.19]);
    shape(group, cone, color, x, y + .14, z, .11,.21,.11);
  } else {
    oval(group, color, [x,y,z], dimensions[kind], kind === "sweet" ? .45 : -.22);
  }
}

function plant(group, [label, type, green, fruitColor, fruit], x, z, size = 1, parts) {
  const model = new T.Group();
  group.add(model);
  model.position.set(x, 0, z);
  model.scale.setScalar(size);
  const height = {root:.75, herb:1.06, bush:1.15, vine:1.65, stalk:1.83, grain:1.4, palm:1.9, tree:1.66}[type];
  const trunk = type === "tree" || type === "palm";
  const structure = new T.Group();
  const foliage = new T.Group();
  const produce = new T.Group();
  model.add(structure, foliage, produce);
  stem(structure, [0,0,0], [0,height,0], trunk ? 0x8a6543 : green, trunk ? .095 : .034);
  const leaves = {root:8, herb:8, bush:10, vine:9, stalk:7, grain:4, palm:8, tree:13}[type];
  for (let i = 0; i < leaves; i++) {
    const angle = i * 2.4;
    const level = trunk ? height * (.72 + .25 * (i % 4) / 3) : height * (.29 + .64 * i / leaves);
    const spread = {root:.3, herb:.28, bush:.44, vine:.37, stalk:.41, grain:.24, palm:.64, tree:.48}[type];
    const x = Math.cos(angle) * spread;
    const z = Math.sin(angle) * spread;
    stem(structure, [0,level,0], [x,level + .13,z], green, .02);
    const length = type === "palm" ? .64 : type === "stalk" || type === "grain" ? .38 : .25;
    const leaf = oval(foliage, green, [x,level + .12,z], [length, type === "tree" ? .15 : .048, .13]);
    leaf.rotation.y = -angle;
    leaf.rotateZ(.25);
  }
  const count = type === "grain" ? 1 : type === "root" ? 3 : 4;
  for (let i = 0; i < count; i++) {
    const angle = i * 2.4 + .65;
    const radius = type === "grain" ? 0 : type === "root" ? .59 : .31;
    const y = type === "root" ? .23 : type === "grain" ? height : height * (.55 + .4 * i / count);
    harvest(produce, fruit, fruitColor, Math.cos(angle) * radius, y, Math.sin(angle) * radius);
  }
  const produceLabel = harvestLabels[fruit] || (label === "Tomate" ? "Tomates" : "Frutos cítricos");
  parts?.push([type === "palm" ? "Pseudotallo" : trunk ? "Tronco y ramas" : "Tallos", structure],
    ["Hojas", foliage], [produceLabel, produce]);
}

function irrigation(group, method, crop, parts) {
  const water = 0x48a8d8;
  const pipes = new T.Group();
  const drops = new T.Group();
  const rows = new T.Group();
  group.add(pipes, drops, rows);
  if (method === "drip") stem(pipes, [-1.23,.09,-.94], [-1.23,.09,.94], 0x26333b, .048);
  for (const z of [-.78, 0, .78]) {
    if (method === "gravity") {
      shape(drops, box, water, 0,.012,z, 2.65,.028,.24);
      shape(pipes, box, 0x98734c, 0,.04,z+.21, 2.72,.08,.14);
    }
    if (method === "drip") {
      stem(pipes, [-1.23,.09,z], [1.13,.09,z], 0x26333b, .033);
      for (const x of [-.77,0,.77]) {
        shape(pipes, cylinder, 0x383e3f, x,.104,z, .073,.08,.073);
        oval(drops, water, [x,.031,z+.1], [.12,.017,.09]);
      }
    }
    for (const x of [-.78, 0, .78]) plant(rows, crop, x, z + .23, .46);
  }
  if (method === "gravity") shape(drops, box, water, -1.25,.02,0, .2,.04,1.81);
  if (method === "rainfed") {
    for (let i = 0; i < 13; i++) {
      oval(drops, water, [Math.cos(i*2.4)*1.18,1.25+(i%4)*.24,Math.sin(i*2.4)*1.03],
        [.034,.091,.034], -.23);
    }
  }
  if (method !== "rainfed") parts.push([method === "drip" ? "Tuberías y goteros" : "Surcos", pipes]);
  parts.push([method === "rainfed" ? "Lluvia" : "Agua", drops], [`Hileras de ${crop[0].toLocaleLowerCase("es")}`, rows]);
}

export function mountGallery({ crop = "mze", irrigation: method = "none" } = {}) {
  const english = window.terraLanguage?.lang === "en";
  const stage = document.querySelector("#scene");
  const renderer = new T.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  stage.append(renderer.domElement);
  const scene = new T.Scene();
  scene.background = new T.Color(0x142c23);
  const camera = new T.PerspectiveCamera(38, 1, .1, 30);
  camera.position.set(3.6, 2.5, 4.1);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.target.set(0, .65, 0);
  orbit.minDistance = 2.6;
  orbit.maxDistance = 8;
  orbit.maxPolarAngle = Math.PI / 2.05;
  orbit.enablePan = false;
  const render = () => renderer.render(scene, camera);
  orbit.addEventListener("change", render);
  scene.add(new T.HemisphereLight(0xf2ffed, 0xb19776, 2.1));
  const light = new T.DirectionalLight(0xffedcd, 2.2);
  light.position.set(4, 6, 3);
  scene.add(light);
  const model = new T.Group();
  scene.add(model);

  const heading = document.querySelector("#model-name");
  const partChoices = document.querySelector("#parts");
  let cropIndex = Math.max(0, cropCodes.indexOf(crop));
  let waterMode = systems.some(([, value]) => value === method) ? method : "none";
  function showParts(parts) {
    partChoices.replaceChildren();
    const options = [["Modelo completo", null], ...parts];
    for (const [label, part] of options) {
      const button = document.createElement("button");
      button.textContent = english
        ? (partEnglish[label] || (label.startsWith("Hileras de ") ? "Crop rows" : label)) : label;
      button.setAttribute("aria-pressed", String(part === null));
      button.addEventListener("click", () => {
        for (const [, group] of parts) group.visible = part === null || part === group;
        for (const choice of partChoices.children) {
          choice.setAttribute("aria-pressed", String(choice === button));
        }
        render();
      });
      partChoices.append(button);
    }
  }
  function addChoice(target, label, select) {
    const button = document.createElement("button");
    button.textContent = label;
    button.addEventListener("click", select);
    document.querySelector(target).append(button);
    return button;
  }
  const cropButtons = crops.map(([label], index) => {
    const control = addChoice("#crops", label, () => {
      cropIndex = index;
      updateModel();
    });
    control.setAttribute("translate", "no");
    return control;
  });
  const waterButtons = new Map(systems.map(([label, value], index) => {
    const button = addChoice("#water", english ? waterEnglish[index] : label, () => {
      waterMode = value;
      updateModel();
    });
    return [value, button];
  }));

  function updateModel() {
    const currentCrop = crops[cropIndex];
    const waterIndex = systems.findIndex(([, value]) => value === waterMode);
    cropButtons.forEach((button, index) => button.setAttribute("aria-pressed", String(index === cropIndex)));
    waterButtons.forEach((button, mode) => button.setAttribute("aria-pressed", String(mode === waterMode)));
    const waterLabel = english ? waterEnglish[waterIndex] : systems[waterIndex][0];
    const cropName = document.createElement("span");
    cropName.setAttribute("translate", "no");
    cropName.textContent = currentCrop[0];
    heading.replaceChildren(cropName);
    if (waterMode !== "none") heading.append(` · ${waterLabel}`);
    model.clear();
    shape(model, box, 0x775537, 0,-.12,0, 2.9,.24,2.4);
    const parts = [];
    if (waterMode === "none") plant(model, currentCrop, 0, 0, 1, parts);
    else irrigation(model, waterMode, currentCrop, parts);
    showParts(parts);
    render();
  }

  function adjust(angle, zoom) {
    const offset = camera.position.clone().sub(orbit.target);
    const spherical = new T.Spherical().setFromVector3(offset);
    spherical.theta += angle;
    spherical.radius = T.MathUtils.clamp(spherical.radius * zoom, orbit.minDistance, orbit.maxDistance);
    camera.position.copy(orbit.target).add(new T.Vector3().setFromSpherical(spherical));
    orbit.update();
  }
  for (const [id, angle, zoom] of [["left",-.35,1],["right",.35,1],["out",0,1.2],["in",0,.83]]) {
    document.getElementById(id).addEventListener("click", () => adjust(angle, zoom));
  }
  new ResizeObserver(() => {
    const { clientWidth: width, clientHeight: height } = stage;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    render();
  }).observe(stage);
  orbit.update();
  updateModel();
  return {
    setIrrigation(mode) {
      if (mode === waterMode || !waterButtons.has(mode)) return;
      waterMode = mode;
      updateModel();
    },
  };
}

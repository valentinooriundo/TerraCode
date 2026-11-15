import * as T from "https://cdn.jsdelivr.net/npm/three@0.179.1/build/three.module.js";

export function createTerraBot() {
  const bot = new T.Group();
  const sphere = new T.SphereGeometry(1, 24, 16);
  const enamel = new T.MeshStandardMaterial({ color: 0xa6e9b2, roughness: 0.36 });
  const teal = new T.MeshStandardMaterial({ color: 0x16816b, roughness: 0.43 });
  const dark = new T.MeshStandardMaterial({ color: 0x102828, roughness: 0.32 });
  const leaf = new T.MeshStandardMaterial({ color: 0x63b942, roughness: 0.65 });
  const light = new T.MeshBasicMaterial({ color: 0xddff8d });

  function ellipsoid(material, position, scale) {
    const part = new T.Mesh(sphere, material);
    part.position.set(...position);
    part.scale.set(...scale);
    bot.add(part);
    return part;
  }

  ellipsoid(enamel, [0,.34,0], [.76,.58,.57]);
  ellipsoid(dark, [0,.34,.43], [.61,.32,.20]);
  ellipsoid(light, [-.22,.38,.618], [.075,.095,.026]);
  ellipsoid(light, [.22,.38,.618], [.075,.095,.026]);
  const smile = new T.QuadraticBezierCurve3(
    new T.Vector3(-.096,.25,.62), new T.Vector3(0,.15,.63), new T.Vector3(.096,.25,.62),
  );
  bot.add(new T.Mesh(new T.TubeGeometry(smile, 12, .021, 8, false), light));
  for (const side of [-1, 1]) {
    ellipsoid(teal, [side*.73,.34,0], [.145,.25,.24]);
    ellipsoid(enamel, [side*.82,.34,0], [.085,.15,.15]);
    ellipsoid(teal, [side*.34,-.29,0], [.13,.14,.15]);
    ellipsoid(enamel, [side*.49,-.42,.015], [.12,.23,.145]).rotation.z = side * .52;
  }
  ellipsoid(enamel, [0,-.41,0], [.42,.37,.37]);
  ellipsoid(teal, [0,-.64,0], [.35,.16,.29]);
  ellipsoid(light, [0,-.77,.015], [.18,.035,.15]);
  ellipsoid(teal, [0,.94,0], [.052,.16,.052]);
  ellipsoid(leaf, [-.13,1.06,0], [.19,.078,.10]).rotation.z = -.5;
  ellipsoid(leaf, [.14,1.12,0], [.22,.088,.10]).rotation.z = .55;
  bot.position.y = -.17;
  return bot;
}

export function mountTerraBot(host) {
  const renderer = new T.WebGLRenderer({ alpha: true, antialias: true });
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(35, 1, .1, 30);
  camera.position.set(0, .1, 3.9);
  const rig = new T.Group();
  rig.add(createTerraBot());
  scene.add(rig, new T.HemisphereLight(0xf5ffec, 0x779391, 2));
  const key = new T.DirectionalLight(0xfff6d4, 2.4);
  key.position.set(2, 4, 3);
  scene.add(key);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.domElement.setAttribute("aria-hidden", "true");
  const resize = () => renderer.setSize(host.clientWidth, host.clientHeight, false);
  resize();
  renderer.render(scene, camera);
  host.append(renderer.domElement);
  host.classList.add("assistant-model-ready");
  new ResizeObserver(resize).observe(host);
  renderer.setAnimationLoop(time => {
    rig.rotation.y = Math.sin(time / 1150) * .32;
    rig.position.y = Math.sin(time / 850) * .045;
    renderer.render(scene, camera);
  });
}

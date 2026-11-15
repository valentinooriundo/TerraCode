const journey = document.querySelector('[data-journey]');
const stage = journey.querySelector('.journey-stage');
const earth = stage.querySelector('img');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const frames = new Map();
let requested;
let queued = false;

function updateEarth() {
  queued = false;
  if (reducedMotion.matches) return;
  const distance = Math.max(1, journey.offsetHeight - stage.offsetHeight);
  const top = parseFloat(getComputedStyle(stage).top) || 0;
  const offset = top - journey.getBoundingClientRect().top;
  const progress = Math.max(0, Math.min(1, offset / distance));
  const longitude = Math.round((-75 + 360 * progress) / 15) * 15;
  const angle = (longitude + 180) % 360 - 180;
  if (requested === angle) return;
  requested = angle;

  let frame = frames.get(angle);
  if (!frame) {
    frame = new Image();
    frame.src = '../earth-' + angle + '.webp';
    frames.set(angle, frame);
  }
  frame.decode().then(() => {
    if (requested === angle) earth.src = frame.src;
  }).catch(() => {});
}

function scheduleEarth() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(updateEarth);
}

addEventListener('scroll', scheduleEarth, { passive: true });
addEventListener('resize', scheduleEarth);
scheduleEarth();

const roster = document.querySelector('#members');
const memberText = window.terraLanguage?.tr || ((es) => es);

async function showMembers() {
  const response = await fetch('equipo.json');
  if (!response.ok) throw new Error('No se pudo cargar el equipo');
  for (const { name, photo, linkedin } of await response.json()) {
    const item = document.createElement('li');
    const initials = document.createElement('span');
    initials.className = 'avatar';
    initials.setAttribute('aria-hidden', 'true');
    initials.textContent = name.split(' ').slice(0, 2).map(word => word[0]).join('');

    if (photo) {
      const image = document.createElement('img');
      Object.assign(image, { className: 'avatar', src: photo, alt: '', loading: 'lazy', width: 48, height: 48 });
      image.addEventListener('error', () => image.replaceWith(initials), { once: true });
      item.append(image);
    } else {
      item.append(initials);
    }
    const label = document.createElement('span');
    label.setAttribute('translate', 'no');
    label.className = 'notranslate';
    label.textContent = name;
    item.append(label);
    const verified = linkedin && /^https:\/\/www\.linkedin\.com\/in\/[\w%-]+\/?$/.test(linkedin);
    const profile = document.createElement('a');
    profile.className = 'member-link';
    profile.href = verified ? linkedin : 'https://www.linkedin.com/search/results/people/?keywords=' + encodeURIComponent(name);
    profile.target = '_blank';
    profile.rel = 'noopener';
    profile.textContent = verified ? 'LinkedIn' : memberText('Buscar en LinkedIn', 'Find on LinkedIn');
    profile.setAttribute('aria-label', profile.textContent + ': ' + name);
    item.append(profile);
    roster.append(item);
  }
}

showMembers().catch(() => {
  const item = document.createElement('li');
  item.textContent = memberText('Consulta la lista en la ficha oficial.', 'See the team on the official project page.');
  roster.replaceChildren(item);
});

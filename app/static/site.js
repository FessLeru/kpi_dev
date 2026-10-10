// Preserve the supplied desktop artwork; fit only illustration boards on small screens.
const media = matchMedia('(max-width: 900px)');
function fitArtwork() {
  document.querySelectorAll('.artwork-shell').forEach(shell => {
    const board = shell.firstElementChild;
    const scale = media.matches ? Math.min(1, shell.clientWidth / Number(board.dataset.width)) : 1;
    board.style.transform = scale < 1 ? `scale(${scale})` : '';
    shell.style.height = media.matches ? `${Number(board.dataset.height) * scale}px` : '';
  });
}
addEventListener('resize', fitArtwork);
fitArtwork();

const filterBar = document.querySelector('.project-filters');
if (filterBar) {
  filterBar.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    const category = button.dataset.filter;
    filterBar.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelector('.project-grid').classList.toggle('projects-filtered', category !== 'all');
    document.querySelectorAll('[data-category]').forEach(card => { card.hidden = category !== 'all' && !card.dataset.category.split(' ').includes(category); });
  });
}

const form = document.querySelector('#inquiry-form');
if (form) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector('[type="submit"]');
    const status = form.querySelector('[role="status"]');
    button.disabled = true;
    status.textContent = 'Сохраняем заявку…';
    const data = new FormData(form);
    try {
      const response = await fetch('/api/inquiries', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: data.get('name'), contact: data.get('contact'), message: data.get('message'), consent: data.get('consent') === 'on' }),
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error('request failed');
      status.textContent = 'Заявка сохранена. Спасибо!';
      form.reset();
    } catch {
      status.textContent = 'Не удалось отправить заявку. Проверьте соединение и попробуйте ещё раз.';
    } finally { button.disabled = false; }
  });
}

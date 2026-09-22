/* Дом в Зыково, v2. Поведение: шапка, меню, появление секций,
   галерея с лайтбоксом, видео по клику, карта по клику, форма. */
(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Шапка: прозрачная над фото, плотная после прокрутки */
  const header = document.querySelector('.header');
  const hero = document.querySelector('.hero');
  function updateHeader() {
    const limit = hero ? Math.max(40, hero.offsetHeight - 140) : 40;
    header.classList.toggle('is-solid', window.scrollY > limit);
  }
  updateHeader();
  window.addEventListener('scroll', updateHeader, { passive: true });
  window.addEventListener('resize', updateHeader);

  /* Мобильное меню */
  const menu = document.getElementById('menu');
  const burger = document.getElementById('burger');
  const menuClose = document.getElementById('menu-close');
  function openMenu() { menu.classList.add('is-open'); document.body.style.overflow = 'hidden'; menuClose.focus(); }
  function closeMenu() { menu.classList.remove('is-open'); document.body.style.overflow = ''; burger.focus(); }
  burger.addEventListener('click', openMenu);
  menuClose.addEventListener('click', closeMenu);
  menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));

  /* Появление секций при прокрутке, один раз */
  const revealTargets = document.querySelectorAll('[data-reveal]');
  if (!reduceMotion && 'IntersectionObserver' in window) {
    revealTargets.forEach((el) => el.classList.add('reveal'));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); io.unobserve(entry.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    revealTargets.forEach((el) => io.observe(el));
  }

  /* Галерея и лайтбокс */
  const items = Array.from(document.querySelectorAll('.gallery__item'));
  const lightbox = document.getElementById('lightbox');
  const lbImg = document.getElementById('lightbox-img');
  const lbCap = document.getElementById('lightbox-cap');
  let current = 0;
  let lastFocus = null;

  function show(i) {
    current = (i + items.length) % items.length;
    const btn = items[current];
    lbImg.src = btn.dataset.full;
    lbImg.alt = btn.querySelector('img').alt;
    lbCap.textContent = btn.dataset.caption || '';
  }
  function openLightbox(i) {
    lastFocus = document.activeElement;
    show(i);
    lightbox.hidden = false;
    document.body.style.overflow = 'hidden';
    document.getElementById('lightbox-close').focus();
  }
  function closeLightbox() {
    lightbox.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  }
  items.forEach((btn, i) => btn.addEventListener('click', () => openLightbox(i)));
  document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
  document.getElementById('lightbox-prev').addEventListener('click', () => show(current - 1));
  document.getElementById('lightbox-next').addEventListener('click', () => show(current + 1));
  lightbox.addEventListener('click', (e) => { if (e.target === lightbox) closeLightbox(); });
  document.addEventListener('keydown', (e) => {
    if (menu.classList.contains('is-open') && e.key === 'Escape') { closeMenu(); return; }
    if (lightbox.hidden) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowRight') show(current + 1);
    if (e.key === 'ArrowLeft') show(current - 1);
  });
  let touchX = 0;
  lightbox.addEventListener('touchstart', (e) => { touchX = e.changedTouches[0].clientX; }, { passive: true });
  lightbox.addEventListener('touchend', (e) => {
    const d = e.changedTouches[0].clientX - touchX;
    if (d > 40) show(current - 1);
    if (d < -40) show(current + 1);
  }, { passive: true });

  /* Видео VK: плеер создаётся только по клику */
  const video = document.getElementById('video-frame');
  const play = document.getElementById('video-play');
  if (video && play) {
    play.addEventListener('click', () => {
      const iframe = document.createElement('iframe');
      iframe.src = 'https://vk.com/video_ext.php?oid=' + video.dataset.oid + '&id=' + video.dataset.vid + '&hd=2&autoplay=1';
      iframe.setAttribute('allow', 'autoplay; fullscreen; picture-in-picture');
      iframe.allowFullscreen = true;
      iframe.title = 'Видеообзор дома в Зыково';
      video.innerHTML = '';
      video.appendChild(iframe);
    });
  }

  /* Карта: включается по клику, чтобы не перехватывать прокрутку */
  const mapOverlay = document.getElementById('map-overlay');
  if (mapOverlay) mapOverlay.addEventListener('click', () => mapOverlay.classList.add('is-hidden'));

  /* Форма */
  const form = document.getElementById('lead-form');
  const nameInput = document.getElementById('name');
  const phoneInput = document.getElementById('phone');
  const consent = document.getElementById('consent');
  const submitBtn = document.getElementById('submit');
  const status = document.getElementById('form-status');
  const success = document.getElementById('form-success');

  phoneInput.addEventListener('focus', function () { if (this.value === '') this.value = '+7 '; });
  phoneInput.addEventListener('input', function () {
    let d = this.value.replace(/\D/g, '');
    if (d.startsWith('8')) d = '7' + d.slice(1);
    if (d.length > 0 && !d.startsWith('7')) d = '7' + d;
    d = d.slice(0, 11);
    let out = '';
    if (d.length > 0) out = '+7';
    if (d.length > 1) out += ' (' + d.slice(1, 4);
    if (d.length >= 4) out += ') ' + d.slice(4, 7);
    if (d.length >= 7) out += '-' + d.slice(7, 9);
    if (d.length >= 9) out += '-' + d.slice(9, 11);
    this.value = out;
    validate();
  });

  function validate() {
    const ok = nameInput.value.trim().length > 0
      && phoneInput.value.replace(/\D/g, '').length === 11
      && consent.checked;
    submitBtn.disabled = !ok;
    return ok;
  }
  nameInput.addEventListener('input', validate);
  consent.addEventListener('change', validate);
  validate();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!validate()) return;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Отправляем…';
    status.textContent = '';
    status.classList.remove('is-error');
    try {
      const res = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('bad status');
      form.hidden = true;
      success.hidden = false;
      success.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Отправить заявку';
      status.textContent = 'Не получилось отправить. Попробуйте ещё раз или позвоните: +7 913 184-10-01.';
      status.classList.add('is-error');
    }
  });
})();

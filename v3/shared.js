/* v3, общий скрипт обоих вариантов: шапка, меню, переключатели картинок,
   галерея с лайтбоксом, видео по клику, поворот дома при прокрутке, форма. */
(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  /* Шапка: прозрачная над первым экраном, плотная после */
  const header = $('.site-header');
  const hero = $('.hero');
  function updateHeader() {
    if (!header) return;
    const limit = hero ? Math.max(40, hero.offsetHeight - 120) : 40;
    header.classList.toggle('is-solid', window.scrollY > limit);
  }
  updateHeader();
  window.addEventListener('scroll', updateHeader, { passive: true });
  window.addEventListener('resize', updateHeader);

  /* Мобильное меню */
  const menu = $('#menu');
  const burger = $('#burger');
  const menuClose = $('#menu-close');
  function openMenu() { menu.classList.add('is-open'); document.body.style.overflow = 'hidden'; menuClose.focus(); }
  function closeMenu() { menu.classList.remove('is-open'); document.body.style.overflow = ''; burger.focus(); }
  if (menu && burger && menuClose) {
    burger.addEventListener('click', openMenu);
    menuClose.addEventListener('click', closeMenu);
    $$('a', menu).forEach((a) => a.addEventListener('click', closeMenu));
  }

  /* Переключатели: фасады, стили интерьера */
  $$('[data-switch]').forEach((box) => {
    const img = $('[data-switch-img]', box);
    const cap = $('[data-switch-cap]', box);
    const note = $('[data-switch-note]', box);
    const buttons = $$('button[data-src]', box);
    function pick(btn) {
      buttons.forEach((b) => { b.classList.toggle('is-active', b === btn); b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
      const swap = () => {
        img.src = btn.dataset.src;
        if (btn.dataset.srcset) img.srcset = btn.dataset.srcset; else img.removeAttribute('srcset');
        img.alt = btn.dataset.alt || btn.textContent.trim();
        if (cap) cap.textContent = btn.dataset.cap || btn.textContent.trim();
        if (note) note.textContent = btn.dataset.note || '';
      };
      if (reduceMotion) { swap(); return; }
      img.classList.add('is-fading');
      const done = () => { img.classList.remove('is-fading'); img.removeEventListener('load', done); };
      setTimeout(() => { img.addEventListener('load', done); swap(); if (img.complete) done(); }, 140);
    }
    buttons.forEach((b) => b.addEventListener('click', () => pick(b)));
    buttons.forEach((b) => { if (b.dataset.src) { const p = new Image(); p.src = b.dataset.src; } });
  });

  /* Галерея и лайтбокс */
  const items = $$('.gallery__item');
  const lightbox = $('#lightbox');
  if (items.length && lightbox) {
    const lbImg = $('#lightbox-img');
    const lbCap = $('#lightbox-cap');
    let current = 0;
    let lastFocus = null;
    function show(i) {
      current = (i + items.length) % items.length;
      const btn = items[current];
      lbImg.src = btn.dataset.full;
      lbImg.alt = $('img', btn).alt;
      lbCap.textContent = btn.dataset.caption || '';
    }
    function openLightbox(i) {
      lastFocus = document.activeElement;
      show(i);
      lightbox.hidden = false;
      document.body.style.overflow = 'hidden';
      $('#lightbox-close').focus();
    }
    function closeLightbox() {
      lightbox.hidden = true;
      document.body.style.overflow = '';
      if (lastFocus) lastFocus.focus();
    }
    items.forEach((btn, i) => btn.addEventListener('click', () => openLightbox(i)));
    $('#lightbox-close').addEventListener('click', closeLightbox);
    $('#lightbox-prev').addEventListener('click', () => show(current - 1));
    $('#lightbox-next').addEventListener('click', () => show(current + 1));
    lightbox.addEventListener('click', (e) => { if (e.target === lightbox) closeLightbox(); });
    document.addEventListener('keydown', (e) => {
      if (menu && menu.classList.contains('is-open') && e.key === 'Escape') { closeMenu(); return; }
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
  }

  /* Видео ВКонтакте: плеер создаётся только по клику */
  const video = $('#video-frame');
  const play = $('#video-play');
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

  /* Поворот дома при прокрутке: лента кадров, кадр выбирается по положению прокрутки */
  const turn = $('[data-turntable]');
  if (turn) {
    const img = $('img', turn);
    const n = parseInt(turn.dataset.frames, 10) || 24;
    const tpl = turn.dataset.src;
    const frames = [];
    let loaded = 0;
    const srcOf = (i) => tpl.replace('{i}', String(i).padStart(2, '0'));
    for (let i = 0; i < n; i++) {
      const im = new Image();
      im.onload = () => { loaded++; if (loaded === n) turn.classList.add('is-ready'); };
      im.onerror = () => { turn.classList.add('is-static'); };
      im.src = srcOf(i);
      frames.push(im);
    }
    let last = -1;
    function update() {
      const box = turn.parentElement;
      const rect = box.getBoundingClientRect();
      const total = box.offsetHeight - window.innerHeight;
      const p = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 0;
      const i = Math.min(n - 1, Math.floor(p * n));
      if (i !== last && frames[i].complete && frames[i].naturalWidth) { img.src = frames[i].src; last = i; }
      const hint = $('[data-turn-hint]', box);
      if (hint) hint.classList.toggle('is-hidden', p > 0.05);
    }
    if (reduceMotion) { turn.classList.add('is-static'); }
    else {
      window.addEventListener('scroll', update, { passive: true });
      window.addEventListener('resize', update);
      update();
    }
  }

  /* Форма: маска телефона, проверка, отправка без перезагрузки */
  const form = $('#lead-form');
  if (form) {
    const nameInput = $('#name');
    const phoneInput = $('#phone');
    const consent = $('#consent');
    const submitBtn = $('#submit');
    const status = $('#form-status');
    const success = $('#form-success');
    const label = submitBtn.textContent;

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
      const ok = nameInput.value.trim().length > 0 && phoneInput.value.replace(/\D/g, '').length === 11 && consent.checked;
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
        submitBtn.textContent = label;
        status.textContent = 'Не получилось отправить. Попробуйте ещё раз или позвоните: +7 913 184-10-01.';
        status.classList.add('is-error');
      }
    });
  }
})();

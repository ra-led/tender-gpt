document.addEventListener('DOMContentLoaded', function(){
  let loading = false;

  // re-usable binders for both initial + injected cards
  function bindAccordion(root){
    root.querySelectorAll('.accordion .toggle-btn').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', () => {
        btn.closest('.accordion').classList.toggle('open');
      });
    });
  }
  function bindSaveCancel(root){
    // SAVE
    root.querySelectorAll('.btn-save').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', function(){
        const card = this.closest('.card');
        card.classList.add('highlighted');
        this.style.display = 'none';
        card.querySelector('.btn-cancel').style.display = 'inline-block';
      });
    });
    // CANCEL
    root.querySelectorAll('.btn-cancel').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', function(){
        const card = this.closest('.card');
        card.classList.remove('highlighted');
        this.style.display = 'none';
        card.querySelector('.btn-save').style.display = 'inline-block';
      });
    });
  }

  // initial bind
  bindAccordion(document);
  bindSaveCancel(document);

  // grab our pagination vars from the template
  const P = window.PAGINATION;

  // IntersectionObserver for “infinite scroll”
  const sentinel = document.getElementById('scroll-sentinel');
  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting && P.hasNext && !loading) {
      loadNextPage();
    }
  }, { rootMargin: '200px' });

  observer.observe(sentinel);

  function loadNextPage(){
    loading = true;
    P.page++;

    const url = `/dashboard/${P.clientId}/data`
              + `?page=${P.page}`
              + `&start_date=${P.startDate}`
              + `&end_date=${P.endDate}`;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        document
          .getElementById('tender-container')
          .insertAdjacentHTML('beforeend', data.html);

        bindAccordion(document.getElementById('tender-container'));
        bindSaveCancel(document.getElementById('tender-container'));

        P.hasNext = data.has_next;
        if (!P.hasNext) {
          document.getElementById('no-more-data').style.display = 'block';
          observer.disconnect();
        }
      })
      .catch(console.error)
      .finally(()=>{ loading = false; });
  }
});
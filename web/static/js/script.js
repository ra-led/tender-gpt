document.addEventListener('DOMContentLoaded', function(){
  let loading = false;

  function bindAccordion(root){
    // ACCORDION
    root.querySelectorAll('.accordion .toggle-btn').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;

        btn.addEventListener('click', () => {
          const accordion = btn.closest('.accordion');
          const card = accordion.closest('.card');
          const wasOpen = accordion.classList.contains('open');
        
          accordion.classList.toggle('open');
        
          if (!accordion.classList.contains('open') && wasOpen) {
            // Accordion just collapsed, scroll card into view
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        
          // if we just opened it, and it was unviewed, mark it viewed
          if (accordion.classList.contains('open')) {
            if (card.classList.contains('unviewed')) {
              const tenderId = card.dataset.tender;
              fetch(`/tender/${tenderId}/viewed`, { method: 'POST' })
                .then(res => {
                  if (res.ok) {
                      // remove the marker class
                      card.classList.remove('unviewed');
                      // remove the badge node itself
                      const badge = card.querySelector('.unviewed-badge');
                      if (badge) badge.remove();
                  }
                })
                .catch(console.error);
            }
          }
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

  const P = window.PAGINATION;

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
              + `&start_date=${encodeURIComponent(P.startDate)}`
              + `&end_date=${encodeURIComponent(P.endDate)}`
              + `&unviewed_only=${P.unviewedOnly}`;

    fetch(url)
      .then(r => r.json())
      .then(data => {
        document
          .getElementById('tender-container')
          .insertAdjacentHTML('beforeend', data.html);

        // re-bind on the newly injected cards
        bindAccordion(document.getElementById('tender-container'));
        bindSaveCancel(document.getElementById('tender-container'));

        P.hasNext = data.has_next;
        if (!P.hasNext) {
          document.getElementById('no-more-data').style.display = 'block';
          observer.disconnect();
        }
      })
      .catch(console.error)
      .finally(() => { loading = false; });
  }
  // export
  const exportLink = document.getElementById('export-link');
  if (exportLink) {
    exportLink.addEventListener('click', e => {
      e.preventDefault();
      // grab client_id and current qs
      const cid = window.PAGINATION.clientId;
      const qs  = window.location.search; 
      // navigate to our new export route
      window.location.href = `/dashboard/${cid}/export${qs}`;
    });
  }
});
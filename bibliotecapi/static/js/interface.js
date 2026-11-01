/* Melhoria progressiva: navegação e formulários funcionam também sem JavaScript. */
(() => {
  'use strict';
  const botao = document.getElementById('alternar-menu');
  const menu = document.getElementById('menu-biblioteca');
  if (botao && menu) {
    const pequeno = window.matchMedia('(max-width: 760px)');
    let aberto = false;
    const atualizar = () => {
      const visivel = !pequeno.matches || aberto;
      const focoNoMenu = menu.contains(document.activeElement);
      const focoNoBotao = document.activeElement === botao;
      botao.hidden = !pequeno.matches;
      menu.hidden = !visivel;
      // Nunca deixe o foco em um item ocultado ao mudar de tamanho.
      if (!visivel && focoNoMenu) botao.focus();
      if (!pequeno.matches && focoNoBotao) menu.querySelector('a')?.focus();
      botao.setAttribute('aria-expanded', String(visivel));
      botao.textContent = visivel ? 'Fechar menu' : 'Menu';
    };
    botao.addEventListener('click', () => { aberto = !aberto; atualizar(); });
    document.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape' && pequeno.matches && aberto &&
          (menu.contains(document.activeElement) || document.activeElement === botao)) {
        evento.preventDefault();
        aberto = false;
        atualizar();
        botao.focus();
      }
    });
    pequeno.addEventListener('change', () => { aberto = false; atualizar(); });
    atualizar();
  }
  const tabelas = document.querySelectorAll('.table-wrap');
  const prepararTabelas = () => tabelas.forEach((tabela) => {
    if (tabela.scrollWidth > tabela.clientWidth) {
      tabela.tabIndex = 0;
      tabela.setAttribute('role', 'region');
      tabela.setAttribute('aria-label', 'Tabela com rolagem horizontal');
    } else {
      tabela.removeAttribute('tabindex');
      tabela.removeAttribute('role');
      tabela.removeAttribute('aria-label');
    }
  });
  prepararTabelas();
  window.addEventListener('resize', prepararTabelas);
  const erros = document.querySelector('[data-foco-erros]');
  if (erros) erros.focus();
})();

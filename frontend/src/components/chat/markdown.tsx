import type { Components } from "react-markdown";

// Overrides compartilhados do ReactMarkdown (bolhas do chat e página compartilhada).
//
// Tabela GFM: o plugin typography estiliza `table` com width:100% + table-layout:auto;
// uma tabela com min-content maior que a bolha vazava e criava barra de rolagem
// horizontal na área de mensagens (pior em mobile, mas também no desktop). O wrapper
// dá scroll interno só à tabela — quando ela cabe, o render é idêntico ao anterior.
export const markdownComponents: Components = {
  table: ({ node: _node, ...props }) => (
    <div className="overflow-x-auto">
      <table {...props} />
    </div>
  ),
};

import { Link } from "react-router-dom";


interface ModeCardProps {
  title: string;
  description: string;
  to: string;
}

export function ModeCard({ title, description, to }: ModeCardProps) {
  return (
    <article className="mode-card">
      <h2>{title}</h2>
      <p>{description}</p>
      <Link className="button button--secondary" to={to} aria-label={title}>进入</Link>
    </article>
  );
}

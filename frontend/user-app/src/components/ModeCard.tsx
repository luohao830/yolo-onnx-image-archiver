import { Link } from "react-router-dom";


interface ModeCardProps {
  title: string;
  description: string;
  to: string;
}

export function ModeCard({ title, description, to }: ModeCardProps) {
  return (
    <article>
      <h2>{title}</h2>
      <p>{description}</p>
      <Link to={to}>{title}</Link>
    </article>
  );
}

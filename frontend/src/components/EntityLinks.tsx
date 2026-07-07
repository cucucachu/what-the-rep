import { Link } from "react-router-dom";

export function JurisdictionLink({
  slug,
  name,
}: {
  slug: string;
  name: string;
}) {
  return <Link to={`/jurisdiction/${slug}`}>{name}</Link>;
}

export function MeetingLink({
  id,
  label,
}: {
  id: string;
  label: string;
}) {
  return <Link to={`/meeting/${id}`}>{label}</Link>;
}

export function ActionLink({
  id,
  label,
}: {
  id: string;
  label: string;
}) {
  return <Link to={`/action/${id}`}>{label}</Link>;
}

export function OfficialLink({
  id,
  name,
}: {
  id: string;
  name: string;
}) {
  return <Link to={`/official/${id}`}>{name}</Link>;
}

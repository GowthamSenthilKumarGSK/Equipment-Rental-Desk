import { Link } from "react-router-dom";
import { useTitle } from "../useTitle";

export default function NotFoundPage() {
  useTitle("Page not found");
  return (
    <>
      <h1>Page not found</h1>
      <p>
        There is nothing at this address. Go to the <Link to="/items">items</Link>,{" "}
        <Link to="/members">members</Link> or <Link to="/overdue">overdue loans</Link>.
      </p>
    </>
  );
}

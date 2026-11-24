import { api, setSession } from "../services/api";
export default function Profile({ user, updateUser, notify }) {
  async function save(e, changePassword) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const result = await api(changePassword ? "/password" : "/profile", {
        method: "PUT",
        body: data,
      });
      if (changePassword) {
        setSession(result);
        form.reset();
      } else updateUser(result);
      notify(
        changePassword
          ? "Password changed. Other sessions have been signed out."
          : "Profile saved",
      );
    } catch (err) {
      notify(err.message, true);
    }
  }
  return (
    <div className="two-col">
      <form className="panel pad form-grid" onSubmit={(e) => save(e, false)}>
        <h3>Personal profile</h3>
        <label>
          Full name
          <input
            name="name"
            defaultValue={user.name}
            required
            maxLength={140}
          />
        </label>
        <label>
          Email address
          <input name="email" type="email" defaultValue={user.email} required />
        </label>
        <button className="btn">Save profile</button>
      </form>
      <form className="panel pad form-grid" onSubmit={(e) => save(e, true)}>
        <h3>Change password</h3>
        <label>
          Current password
          <input
            name="current"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <label>
          New password (12–128 characters)
          <input
            name="password"
            type="password"
            minLength={12}
            maxLength={128}
            required
            autoComplete="new-password"
          />
        </label>
        <button className="btn btn-secondary">Change password</button>
      </form>
    </div>
  );
}

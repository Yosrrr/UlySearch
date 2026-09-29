import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate("/");
    } catch (err) {
      const backendMessage = err.response?.data?.detail;
      setError(
        backendMessage ||
          "Connexion impossible — vérifiez l'adresse e-mail et le mot de passe."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-xl">
        <div className="mb-6 text-center">
          <p className="text-xl font-semibold text-ink-900">UlySearch</p>
          <p className="text-sm text-slate-500">Veille des appels d'offres</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-300 bg-rose-50 px-4 py-2.5 text-sm text-rose-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-ink-900">
              Adresse e-mail
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-ink-700"
              placeholder="prenom.nom@sotradies.tn"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-ink-900">
              Mot de passe
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm focus:border-ink-700"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-ink-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-ink-700 disabled:opacity-60"
          >
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        {/* Séparateur */}
        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-200" />
          <span className="text-xs text-slate-400">ou</span>
          <div className="h-px flex-1 bg-slate-200" />
        </div>

        {/* Bouton inscription */}
        <button
          onClick={() => navigate("/register")}
          className="w-full rounded-lg border-2 border-amber-500 px-4 py-2.5 text-sm font-medium text-amber-600 hover:bg-amber-50"
        >
          Créer mon compte gratuitement
        </button>

        <p className="mt-4 text-center text-xs text-slate-400">
          Configurez votre veille en 5 minutes avec l'aide de l'IA
        </p>
      </div>
    </div>
  );
}
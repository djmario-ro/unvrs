import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import toast from "react-hot-toast";

import { login } from "../api/auth";
import { useMe } from "../hooks/useMe";
import Spinner from "../components/Spinner";
import retreat from "../assets/retreat.webp";

export default function LoginPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: user, isLoading } = useMe();
  const [form, setForm] = useState({ username: "", password: "" });

  const loginMutation = useMutation({
    mutationFn: () => login(form.username, form.password),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      nav("/app", { replace: true });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#ebe1d7]">
        <Spinner size={32} />
      </div>
    );
  }
  if (user) return <Navigate to="/app" replace />;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (form.username && form.password) loginMutation.mutate();
  };

  return (
    <div className="min-h-screen flex bg-[#ebe1d7]">
      {/* Brand / splash — the guesthouse itself */}
      <div className="hidden lg:flex lg:w-[56%] relative flex-col items-center justify-center px-12">
        <img
          src={retreat}
          alt="The guesthouse"
          className="w-full max-w-2xl object-contain select-none"
          draggable={false}
        />
        <div className="text-center -mt-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.35em] text-[#b8492e]">
            Retreat 480
          </p>
          <h1 className="font-serif text-4xl text-[#463a2e] mt-2 tracking-tight">
            An old mountain retreat, reborn.
          </h1>
          <p className="text-[#8a7a66] mt-2 tracking-wide">
            Secluded · Tranquil · Natural
          </p>
        </div>
      </div>

      {/* Sign-in */}
      <div className="flex-1 flex items-center justify-center p-6 bg-white lg:rounded-l-[2.5rem] lg:shadow-[-20px_0_60px_-30px_rgba(70,58,46,0.5)]">
        <div className="w-full max-w-sm">
          {/* Compact brand for small screens */}
          <div className="lg:hidden flex flex-col items-center mb-6">
            <img
              src={retreat}
              alt="The guesthouse"
              className="w-52 object-contain rounded-xl"
              draggable={false}
            />
            <h1 className="font-serif text-2xl text-[#463a2e] mt-1">Retreat 480</h1>
          </div>

          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-gray-900">Welcome back</h2>
            <p className="text-sm text-gray-500 mt-1">Sign in to your staff account.</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="username">
                Username
              </label>
              <input
                id="username"
                className="input"
                autoFocus
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              />
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </div>
            <button
              type="submit"
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#b8492e] hover:bg-[#a4402a] text-white font-medium py-2.5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={!form.username || !form.password || loginMutation.isPending}
            >
              {loginMutation.isPending ? "Signing in…" : "Sign in"}
              <LogIn size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

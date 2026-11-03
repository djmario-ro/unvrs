import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import api from "../api/client";
import { useMe } from "../hooks/useMe";
export default function PropertiesPage() {
  const { data: me } = useMe();
  const [name, setName] = useState(""),
    [slug, setSlug] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api
        .post<{ id: number }>("/properties", { name, slug })
        .then((r) => r.data),
    onSuccess: (p) => {
      sessionStorage.setItem("unvrs-property", String(p.id));
      window.location.assign("/app");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="p-4 sm:p-8 space-y-6">
      <h1 className="text-2xl font-bold">Properties</h1>
      <div className="card p-5 space-y-2">
        {me?.properties.map((p) => (
          <div key={p.id} className="flex justify-between">
            <span>{p.name}</span>
            <span className="capitalize text-sm text-gray-500">
              {p.roles.join(", ")}
            </span>
          </div>
        ))}
      </div>
      <form
        className="card p-5 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <h2 className="font-semibold">Create a property</h2>
        <label className="label">
          Name
          <input
            className="input"
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="label">
          Unique URL name
          <input
            className="input"
            required
            maxLength={100}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            placeholder="my-property"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
        </label>
        <p className="text-sm text-gray-500">
          You become its owner. Door and messaging integrations require separate
          operator configuration.
        </p>
        <button className="btn-primary" disabled={create.isPending}>
          Create property
        </button>
      </form>
    </div>
  );
}

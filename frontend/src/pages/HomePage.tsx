import { useCallback, useMemo, useState } from "react";

import { WhatTheRepMcpClient } from "../mcp/client.js";
import { McpWidget } from "../components/McpWidget.js";
import "./HomePage.css";

export const NOVATO_CITY_HALL = { lat: 38.1074, lng: -122.5697 };

const OUTSIDE_COVERAGE_MESSAGE =
  "This location is outside our pilot coverage area (Novato & Marin County).";

type Jurisdiction = {
  slug: string;
  name: string;
  level?: string;
};

export type ResolveLocationResult = {
  covered: boolean;
  lat: number;
  lng: number;
  message?: string;
  jurisdictions: Jurisdiction[];
};

export type HomePageProps = {
  client?: WhatTheRepMcpClient;
};

type LocationPhase =
  | { kind: "prompt"; showManualForm: boolean; geoError: string | null }
  | { kind: "resolving" }
  | { kind: "covered"; slugs: string[] }
  | { kind: "outside"; message: string }
  | { kind: "error"; message: string };

const initialPromptPhase: Extract<LocationPhase, { kind: "prompt" }> = {
  kind: "prompt",
  showManualForm: false,
  geoError: null,
};

export function HomePage({ client: clientProp }: HomePageProps) {
  const client = useMemo(
    () => clientProp ?? new WhatTheRepMcpClient(),
    [clientProp],
  );
  const [phase, setPhase] = useState<LocationPhase>(initialPromptPhase);
  const [manualLat, setManualLat] = useState("");
  const [manualLng, setManualLng] = useState("");

  const resolveLocation = useCallback(
    async (lat: number, lng: number) => {
      setPhase({ kind: "resolving" });

      try {
        if (!client.isConnected()) {
          await client.connect();
        }

        const result = (await client.callTool("resolve_location", {
          lat,
          lng,
        })) as ResolveLocationResult;

        if (!result.covered) {
          setPhase({
            kind: "outside",
            message: result.message ?? OUTSIDE_COVERAGE_MESSAGE,
          });
          return;
        }

        const slugs = result.jurisdictions.map((jurisdiction) => jurisdiction.slug);
        setPhase({ kind: "covered", slugs });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Failed to resolve location";
        setPhase({ kind: "error", message });
      }
    },
    [client],
  );

  const handleUseMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setPhase({
        kind: "prompt",
        showManualForm: true,
        geoError: "Geolocation is not available in this browser.",
      });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        void resolveLocation(
          position.coords.latitude,
          position.coords.longitude,
        );
      },
      (error) => {
        const denied = error.code === error.PERMISSION_DENIED;
        setPhase({
          kind: "prompt",
          showManualForm: true,
          geoError: denied
            ? "Location access was denied. Enter your coordinates below."
            : "Could not detect your location. Enter your coordinates below.",
        });
      },
    );
  }, [resolveLocation]);

  const handleTryNovato = useCallback(() => {
    void resolveLocation(NOVATO_CITY_HALL.lat, NOVATO_CITY_HALL.lng);
  }, [resolveLocation]);

  const handleManualSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const lat = Number.parseFloat(manualLat);
      const lng = Number.parseFloat(manualLng);
      if (Number.isNaN(lat) || Number.isNaN(lng)) {
        return;
      }
      void resolveLocation(lat, lng);
    },
    [manualLat, manualLng, resolveLocation],
  );

  const showManualForm =
    phase.kind === "prompt" ? phase.showManualForm : false;

  return (
    <section className="home-page" aria-label="Home page">
      {phase.kind === "resolving" ? (
        <p className="home-page__status" role="status">
          Resolving your location…
        </p>
      ) : null}

      {phase.kind === "prompt" ? (
        <div className="home-page__location">
          <h2>Where are you?</h2>
          <p className="home-page__intro">
            We use your location to show what your local governments are doing.
          </p>

          <div className="home-page__actions">
            <button type="button" onClick={handleUseMyLocation}>
              Use my location
            </button>
            <button type="button" onClick={handleTryNovato}>
              Try Novato
            </button>
            {!showManualForm ? (
              <button
                type="button"
                className="home-page__link-button"
                onClick={() =>
                  setPhase({
                    kind: "prompt",
                    showManualForm: true,
                    geoError: null,
                  })
                }
              >
                Enter coordinates manually
              </button>
            ) : null}
          </div>

          {phase.geoError ? (
            <p className="home-page__geo-error" role="status">
              {phase.geoError}
            </p>
          ) : null}

          {showManualForm ? (
            <form
              className="home-page__manual-form"
              aria-label="Manual coordinates"
              onSubmit={handleManualSubmit}
            >
              <label>
                Latitude
                <input
                  type="text"
                  inputMode="decimal"
                  name="lat"
                  value={manualLat}
                  onChange={(event) => setManualLat(event.target.value)}
                  placeholder="e.g. 38.1074"
                  required
                />
              </label>
              <label>
                Longitude
                <input
                  type="text"
                  inputMode="decimal"
                  name="lng"
                  value={manualLng}
                  onChange={(event) => setManualLng(event.target.value)}
                  placeholder="e.g. -122.5697"
                  required
                />
              </label>
              <label className="home-page__address-label">
                Address
                <input
                  type="text"
                  name="address"
                  disabled
                  placeholder="Address lookup coming soon"
                  aria-disabled="true"
                />
              </label>
              <button type="submit">Look up location</button>
            </form>
          ) : null}
        </div>
      ) : null}

      {phase.kind === "outside" ? (
        <div className="home-page__coverage" role="status">
          <h2>Outside pilot coverage</h2>
          <p>{phase.message}</p>
          <button
            type="button"
            onClick={() => setPhase(initialPromptPhase)}
          >
            Try a different location
          </button>
        </div>
      ) : null}

      {phase.kind === "error" ? (
        <div className="home-page__error" role="alert">
          <p>{phase.message}</p>
          <button
            type="button"
            onClick={() => setPhase(initialPromptPhase)}
          >
            Try again
          </button>
        </div>
      ) : null}

      {phase.kind === "covered" ? (
        <div className="home-page__summary" aria-label="Home summary">
          <McpWidget
            client={client}
            toolName="get_home_summary"
            toolArgs={{ jurisdiction_slugs: phase.slugs }}
          />
        </div>
      ) : null}
    </section>
  );
}

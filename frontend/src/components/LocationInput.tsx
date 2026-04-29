import { useState, useRef, useCallback, useEffect } from "react";
import type { Location, NominatimResult } from "../types/trip";

interface Props {
  label: string;
  value: Location | null;
  onChange: (loc: Location) => void;
  placeholder?: string;
}

const LocationInput = ({ label, value, onChange, placeholder }: Props) => {
  const [typedQuery, setTypedQuery] = useState("");
  const [selectedName, setSelectedName] = useState(value?.name || "");
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const displayValue = isFocused ? typedQuery : selectedName || typedQuery;

  const search = useCallback(async (q: string) => {
    if (q.length < 3) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=5&addressdetails=1&q=${encodeURIComponent(q)}`,
        { headers: { "User-Agent": "ELDTripPlanner/1.0" } }
      );
      const data: NominatimResult[] = await resp.json();
      setResults(data);
      setOpen(data.length > 0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setTypedQuery(v);
    setSelectedName("");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => search(v), 500);
  };

  const handleSelect = (r: NominatimResult) => {
    const loc: Location = {
      lat: parseFloat(r.lat),
      lon: parseFloat(r.lon),
      name: r.display_name,
    };
    setTypedQuery(r.display_name);
    setSelectedName(r.display_name);
    setOpen(false);
    setIsFocused(false);
    onChange(loc);
  };

  const handleFocus = () => {
    setIsFocused(true);
    if (!typedQuery && selectedName) setTypedQuery(selectedName);
    if (results.length > 0) setOpen(true);
  };

  const handleBlur = () => setIsFocused(false);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setIsFocused(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <input
        type="text"
        value={displayValue}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
      />
      {loading && (
        <div className="absolute right-3 top-9">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500" />
        </div>
      )}
      {open && results.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg max-h-60 overflow-y-auto">
          {results.map((r) => (
            <li
              key={r.place_id}
              onClick={() => handleSelect(r)}
              className="cursor-pointer px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-700 transition-colors"
            >
              {r.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default LocationInput;

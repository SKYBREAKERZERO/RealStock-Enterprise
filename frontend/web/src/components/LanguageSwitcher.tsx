import {
  Languages,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";


export function LanguageSwitcher() {
  const {
    i18n,
  } = useTranslation();

  const language =
    i18n.language
      .startsWith("zh")
      ? "zh-CN"
      : "en-US";


  async function setLanguage(
    nextLanguage:
      | "zh-CN"
      | "en-US",
  ) {
    await i18n.changeLanguage(
      nextLanguage,
    );
  }


  return (
    <div
      className={
        "language-switcher"
      }
    >
      <Languages
        size={16}
      />

      <button
        type="button"
        className={
          language === "zh-CN"
            ? "active"
            : ""
        }
        onClick={() => {
          void setLanguage(
            "zh-CN",
          );
        }}
      >
        中文
      </button>

      <span>
        /
      </span>

      <button
        type="button"
        className={
          language === "en-US"
            ? "active"
            : ""
        }
        onClick={() => {
          void setLanguage(
            "en-US",
          );
        }}
      >
        EN
      </button>
    </div>
  );
}
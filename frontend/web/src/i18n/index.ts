import i18n from "i18next";

import {
  initReactI18next,
} from "react-i18next";

import {
  enUS,
} from "./en-US";

import {
  zhCN,
} from "./zh-CN";


const STORAGE_KEY =
  "realstock-language";


function resolveInitialLanguage():
  | "zh-CN"
  | "en-US" {
  const stored =
    localStorage.getItem(
      STORAGE_KEY,
    );

  if (
    stored === "zh-CN"
    || stored === "en-US"
  ) {
    return stored;
  }

  const browserLanguage =
    navigator.language
      .toLowerCase();

  if (
    browserLanguage.startsWith(
      "zh",
    )
  ) {
    return "zh-CN";
  }

  return "en-US";
}


void i18n
  .use(
    initReactI18next,
  )
  .init({
    resources: {
      "en-US": {
        translation:
          enUS,
      },

      "zh-CN": {
        translation:
          zhCN,
      },
    },

    lng:
      resolveInitialLanguage(),

    fallbackLng:
      "en-US",

    interpolation: {
      escapeValue: false,
    },

    returnNull: false,
  });


i18n.on(
  "languageChanged",
  (language) => {
    if (
      language === "zh-CN"
      || language === "en-US"
    ) {
      localStorage.setItem(
        STORAGE_KEY,
        language,
      );

      document.documentElement.lang =
        language;
    }
  },
);


document.documentElement.lang =
  i18n.language;


export default i18n;
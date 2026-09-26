import {
  Settings,
} from "lucide-react";

import {
  useTranslation,
} from "react-i18next";

import {
  LanguageSwitcher,
} from "../components/LanguageSwitcher";


export function SettingsPage() {
  const {
    i18n,
  } = useTranslation();

  const isZh =
    i18n.language.startsWith("zh");

  return (
    <section
      className="page-section"
    >
      <div
        className="page-card"
      >
        <div
          className="page-card-header"
        >
          <div>
            <h2>
              {isZh
                ? "设置"
                : "Settings"}
            </h2>

            <p>
              {isZh
                ? "RealStock Enterprise 用户界面设置。"
                : "RealStock Enterprise user interface settings."}
            </p>
          </div>

          <Settings
            size={20}
          />
        </div>


        <div
          className="settings-row"
        >
          <div>
            <strong>
              {isZh
                ? "界面语言"
                : "Interface Language"}
            </strong>

            <span>
              {isZh
                ? (
                  "语言偏好会保存到本地浏览器。"
                )
                : (
                  "Your language preference "
                  + "is stored in this browser."
                )}
            </span>
          </div>

          <LanguageSwitcher />
        </div>
      </div>
    </section>
  );
}
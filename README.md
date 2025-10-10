# M Village Email Templates

A comprehensive collection of email templates for M Village hotel booking platform, supporting multiple languages (English/Vietnamese) and various customer journey touchpoints.

## 📋 Table of Contents

- [Template Categories](#-template-categories)
- [Quick Start](#-quick-start)
- [Template Variables](#-template-variables)
- [Technical Specifications](#-technical-specifications)
- [Automation Tools](#-automation-tools)
- [Process Documentation](#-process-documentation)
- [Usage Guidelines](#-usage-guidelines)
- [Support](#-support)

## 📁 Template Categories

### 🏨 Booking Confirmations
- **1.bk-loyalty/** - Booking confirmations for loyalty program members
  - `bk-conf-EN.html` - English version
  - `bk-conf-VI.html` - Vietnamese version

- **2.bk-non-loyalty/** - Booking confirmations for non-loyalty customers
  - `bk-conf-non-loyalty-EN.html` - English version
  - `bk-conf-non-loyalty-VI.html` - Vietnamese version

- **3.bk-b2b/** - B2B booking confirmations
  - `bk-conf-b2b-EN.html` - English version
  - `bk-conf-b2b-VI.html` - Vietnamese version

### 🎯 Customer Journey & Onboarding
- **9.welcome/** - Welcome emails for new users
  - `email_welcome_en.html` - English welcome
  - `email_welcome_vi.html` - Vietnamese welcome

- **8.verify/** - Email verification
  - `verify.html` - Account verification email

- **10.remind-verify/** - Verification reminders
  - `remind-verify-EN.html` - English reminder
  - `remind-verify-VI.html` - Vietnamese reminder

- **22.pre-arrival/** - Pre-arrival notifications
  - `pre-arrival_en.html` - English pre-arrival
  - `pre-arrival_vi.html` - Vietnamese pre-arrival

### 📊 Surveys & Feedback Collection
- **6.survey-loyalty/** - Post-stay surveys for loyalty members
  - `survey-loyalty-EN.html` - English survey
  - `survey-loyalty-VI.html` - Vietnamese survey

- **7.survey-non-loyalty/** - Post-stay surveys for non-loyalty customers
  - `survey-non-loyalty-EN.html` - English survey
  - `survey-non-loyalty-VI.html` - Vietnamese survey

- **17.start-review-loyalty/** - Review initiation for loyalty members
  - `start-review-loyalty-EN.html` - English version
  - `start-review-loyalty-VI.html` - Vietnamese version

- **18.end-review-loyalty/** - Review completion for loyalty members
  - `end-review-loyalty-EN.html` - English version
  - `end-review-loyalty-VI.html` - Vietnamese version

### 💰 Billing & Financial
- **5.einvoice/** - Electronic invoice templates
  - `einvoice-email.html` - Email invoice template
  - `einvoice-pms-template.html` - PMS invoice template
  - `einvoice-pms-updated.html` - Updated PMS template
  - `invoice-v2.html` - Version 2 invoice template

### 🏢 B2B & Corporate Solutions
- **4.b2b lead/** - B2B lead generation
  - `b2b.html` - B2B lead capture template

- **19.b2b-reminder/** - B2B follow-up reminders
  - `b2b-bao-gia.html` - Vietnamese pricing reminder
  - `b2b-reminder-v2-en.html` - English B2B reminder v2
  - `b2b-reminder-v2-vi.html` - Vietnamese B2B reminder v2

- **21.b2b-send-pass/** - B2B account credentials
  - `b2b-send-pass-en.html` - English credentials
  - `b2b-send-pass-vi.html` - Vietnamese credentials

- **24.b2b-recontact/** - B2B re-engagement
  - `b2b-combine.html` - Combined B2B recontact template

### 🎖️ Loyalty Program Management
- **13.upgrade-tier/** - Tier upgrade notifications
  - `upgrade_tier_en.html` - English upgrade
  - `upgrade_tier_vi.html` - Vietnamese upgrade

- **14.downgrade-tier/** - Tier downgrade notifications
  - `downgrade_tier_en.html` - English downgrade
  - `downgrade_tier_vi.html` - Vietnamese downgrade

### 🏠 Property Management
- **23.landlord/** - Landlord-specific templates
  - `landlord.html` - Main landlord template
  - `landlord-demo.html` - Demo version

### 🛠️ Tools & Utilities
- **12.tool/** - Utility templates and tools
  - `account_deletion_tool.html` - Account deletion template
  - `landlord-landing-page.html` - Landlord landing page
  - `original.html` - Original template
  - `survey-typeform-v1.html` - Typeform survey integration

### ⚠️ Issue Management
- **20.aware-issue/** - Issue awareness notifications
  - `aware-EN.html` - English issue notification
  - `aware-VI.html` - Vietnamese issue notification

## 🚀 Quick Start

### Using Templates
1. Choose the appropriate template from the categorized folders
2. Replace template variables with actual data
3. Test across different email clients
4. Deploy through your email service provider

### Template Variables
Most templates use Handlebars-style variables for dynamic content:

#### Common Variables
- `{{email}}` - Customer email address
- `{{name}}` - Customer full name
- `{{first_name}}` - Customer first name
- `{{last_name}}` - Customer last name
- `{{booking_id}}` - Booking reference number
- `{{hotel_name}}` - Hotel name
- `{{check_in_date}}` - Check-in date
- `{{check_out_date}}` - Check-out date
- `{{room_type}}` - Room type
- `{{total_amount}}` - Total booking amount
- `{{currency}}` - Currency code

#### B2B Specific Variables
- `{{company_name}}` - Company name
- `{{contact_person}}` - Contact person name
- `{{work_email}}` - Work email address
- `{{phone_number}}` - Phone number
- `{{hotel_city}}` - Hotel city location
- `{{budget_per_night}}` - Budget per night

## 🔧 Technical Specifications

### HTML & CSS Standards
- **HTML5** - Modern semantic HTML structure
- **CSS3** - Inline and embedded styles for maximum compatibility
- **Responsive Design** - Mobile-first approach with media queries
- **Cross-client Compatibility** - Tested across major email clients

### Email Client Support
- ✅ Outlook (2007-2019, Office 365)
- ✅ Gmail (Web, Mobile, Desktop)
- ✅ Apple Mail (macOS, iOS)
- ✅ Yahoo Mail
- ✅ Thunderbird
- ✅ Mobile clients (iOS Mail, Android Gmail)

### Typography & Branding
- **Primary Font**: Be Vietnam Pro (Google Fonts)
- **Fallback Fonts**: Arial, Helvetica, sans-serif
- **Character Encoding**: UTF-8
- **MIME Type**: text/html

### Performance Features
- **Optimized Images** - Compressed and web-optimized
- **Minified CSS** - Reduced file sizes
- **Fast Loading** - Optimized for quick rendering
- **Accessibility** - Screen reader friendly with proper ARIA labels

## 🤖 Automation Tools

### Python Scripts
- **15.python/send-b2b-lead.py** - Automated B2B lead email sending
  ```bash
  cd 15.python
  python send-b2b-lead.py
  ```
  
  **Features:**
  - CSV data import
  - API integration with M Village backend
  - Batch processing with error handling
  - Success/failure logging

### Data Processing
- **15.python/Updated_Trip - VAT.ipynb** - Jupyter notebook for data analysis and VAT calculations

## 📈 Process Documentation

### Flowcharts
- **16.flowchart-mermaidchart/MV-pickup-profile.mmd** - Profile pickup process flowchart
- **16.flowchart-mermaidchart/MV-product-process.mmd** - Product development process flowchart

These Mermaid charts document the internal processes and can be rendered using Mermaid-compatible tools.

## 📝 Usage Guidelines

### Best Practices
1. **Always test templates** in multiple email clients before deployment
2. **Use semantic HTML** for better accessibility and deliverability
3. **Optimize images** for web delivery (WebP, compressed JPEG/PNG)
4. **Maintain consistent branding** across all templates
5. **Follow responsive design** principles for mobile compatibility

### Customization
- Templates are designed to be easily customizable
- Maintain the core structure while updating content and styling
- Test thoroughly after any modifications
- Keep backup copies of original templates

### Language Support
- **English (EN)** - Full English templates with proper grammar and tone
- **Vietnamese (VI)** - Full Vietnamese templates with cultural considerations
- **Bilingual Consistency** - Maintained messaging and branding across languages

## 🎨 Design Features

### Visual Elements
- **Professional Layout** - Clean, modern design aesthetic
- **Brand Consistency** - M Village colors, fonts, and imagery
- **Responsive Grid** - Adapts to different screen sizes
- **Call-to-Action Buttons** - Prominent, accessible action buttons

### Accessibility
- **Screen Reader Support** - Proper ARIA labels and semantic HTML
- **High Contrast** - Readable color combinations
- **Keyboard Navigation** - Accessible via keyboard controls
- **Alt Text** - Descriptive alternative text for images

## 📞 Support & Maintenance

### Getting Help
For questions about template usage, customization, or technical issues:
- Contact the M Village development team
- Check existing documentation in this repository
- Review the process flowcharts for workflow guidance

### Contributing
When adding new templates or modifying existing ones:
1. Follow the established naming conventions
2. Maintain bilingual support (EN/VI)
3. Test across multiple email clients
4. Update this README with new template information
5. Follow the existing folder structure and organization

### Version Control
- All templates are version controlled in Git
- Use descriptive commit messages
- Tag major releases and updates
- Maintain backward compatibility when possible

---

**Last Updated**: December 2024  
**Version**: 2.0  
**Maintained by**: M Village Development Team
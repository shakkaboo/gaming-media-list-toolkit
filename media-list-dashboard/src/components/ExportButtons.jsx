import React from 'react';
import { FileText, FileSpreadsheet } from 'lucide-react';
import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

const ExportButtons = ({ data, filename = 'Global_Media_List' }) => {
  const handleExportExcel = () => {
    // Format data for export
    const exportData = data.map((item, index) => ({
      'Rank': index + 1,
      'Publication Name': item['Publication Name'],
      'Category': item['Category'],
      'Target Market': item['Target Market'] || item['Country'],
      'Growth Rate': item['Growth Rate'] || '0%',
      'Est. Monthly Pageviews': item['Estimated Monthly Pageviews'],
      'Traffic Source URL': item['Traffic Source URL'],
      'Contact Email': item['Contact Email'],
      'Website URL': item['Website URL'],
      'Qualification Status': item['Qualification Status']
    }));

    const worksheet = XLSX.utils.json_to_sheet(exportData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Media List');
    XLSX.writeFile(workbook, `${filename}.xlsx`);
  };

  const handleExportPDF = () => {
    const doc = new jsPDF();
    
    doc.text('Global Gaming Media Rankings', 14, 15);
    
    const tableColumn = ["Rank", "Publication Name", "Category", "Target Market", "Growth", "Est. Pageviews"];
    const tableRows = [];

    data.forEach((item, index) => {
      let pageviews = item['Estimated Monthly Pageviews'];
      if (typeof pageviews === 'number') {
        pageviews = new Intl.NumberFormat('en-US').format(pageviews);
      }
      const rowData = [
        index + 1,
        item['Publication Name'],
        item['Category'],
        item['Target Market'] || item['Country'],
        item['Growth Rate'] || '0%',
        pageviews
      ];
      tableRows.push(rowData);
    });

    doc.autoTable({
      head: [tableColumn],
      body: tableRows,
      startY: 20,
      theme: 'grid',
      styles: { fontSize: 8 },
      headStyles: { fillColor: [69, 162, 158] }
    });

    doc.save(`${filename}.pdf`);
  };

  return (
    <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', justifyContent: 'flex-end' }}>
      <button 
        onClick={handleExportExcel}
        className="glass-panel"
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', color: 'var(--text-bright)', padding: '0.75rem 1.5rem', background: 'rgba(31, 40, 51, 0.8)' }}
      >
        <FileSpreadsheet size={18} color="#4ade80" />
        Export to Excel
      </button>
      <button 
        onClick={handleExportPDF}
        className="glass-panel"
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', color: 'var(--text-bright)', padding: '0.75rem 1.5rem', background: 'rgba(31, 40, 51, 0.8)' }}
      >
        <FileText size={18} color="#f87171" />
        Export to PDF
      </button>
    </div>
  );
};

export default ExportButtons;

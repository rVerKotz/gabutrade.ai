import { NextResponse } from 'next/server';

/**
 * API Route untuk memproses permintaan deposit manual.
 * Menerima detail dari user dan menghasilkan invoice transfer.
 */
export async function POST(req: Request) {
  try {
    const { amount, userBank, userAccountName, userId } = await req.json();

    // Validasi input
    if (!amount || amount < 100) {
      return NextResponse.json({ error: 'Minimal deposit adalah $100' }, { status: 400 });
    }
    if (!userBank || !userAccountName) {
      return NextResponse.json({ error: 'Detail bank pengirim wajib diisi' }, { status: 400 });
    }

    // Buat kode unik (3 digit terakhir)
    const uniqueCode = Math.floor(100 + Math.random() * 899);
    // Jumlah yang harus ditransfer (Amount + 0.uniqueCode)
    const amountToPay = Math.floor(amount) + (uniqueCode / 1000);
    
    const referenceId = `DEP-${userId.substring(0, 5)}-${Date.now().toString().slice(-6)}`;

    // Simulasi penyimpanan ke database (Disini Anda bisa simpan status "PENDING")
    const bankInstructions = {
      reference_id: referenceId,
      sender_info: `${userAccountName} (${userBank})`,
      amount_to_pay: amountToPay,
      unique_code: uniqueCode,
      timestamp: new Date().toISOString()
    };

    console.log(`[DEPOSIT LOG] ${referenceId} created for ${userAccountName} via ${userBank}`);

    return NextResponse.json({ 
      success: true, 
      instructions: bankInstructions 
    });

  } catch (err: any) {
    console.error("Manual Deposit API Error:", err);
    return NextResponse.json(
      { error: 'Gagal memproses permintaan deposit' },
      { status: 500 }
    );
  }
}